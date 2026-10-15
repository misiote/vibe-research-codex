using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Diagnostics;
using Microsoft.Web.WebView2.WinForms;

namespace VibeResearchCompanion;

internal static class Program
{
    private static Mutex? instanceMutex;

    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        var options = ParseArguments(args);
        if (!options.TryGetValue("--url", out var url))
            throw new ArgumentException("missing --url");
        if (!AcquireInstanceLock(options.GetValueOrDefault("--pid-file"))) return;

        Application.Run(new CompanionButtonForm(
            url,
            options.GetValueOrDefault("--title", "Vibe Research · 研究现场"),
            options.GetValueOrDefault("--ui-state"),
            options.GetValueOrDefault("--pid-file"),
            options.GetValueOrDefault("--control-file")));
    }

    private static Dictionary<string, string> ParseArguments(string[] args)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index + 1 < args.Length; index += 2)
            result[args[index]] = args[index + 1];
        return result;
    }

    private static bool AcquireInstanceLock(string? pidFilePath)
    {
        if (string.IsNullOrWhiteSpace(pidFilePath)) return true;
        var digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Path.GetFullPath(pidFilePath).ToUpperInvariant())))[..20];
        instanceMutex = new Mutex(true, "Local\\VibeResearchCompanion-" + digest, out var created);
        return created;
    }
}

internal sealed class ResearchCompanionButton : Control
{
    public event EventHandler? KeyboardActivate;
    public double MotionPhase { get; set; }
    public Color StatusColor { get; set; } = Color.FromArgb(31, 224, 150);

    public ResearchCompanionButton()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true);
        Cursor = Cursors.Hand;
        SetStyle(ControlStyles.Selectable, true);
        TabStop = true;
        AccessibleName = "打开研究现场";
        AccessibleRole = AccessibleRole.PushButton;
        AccessibleDescription = "打开 Vibe Research 研究现场；拖拽可移动入口";
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        g.Clear(Color.Magenta);
        var ring = new RectangleF(3.2f, 3.2f, Width - 6.4f, Height - 6.4f);
        for (var index = 0; index < 18; index++)
        {
            var distance = (index / 18d - MotionPhase / (Math.PI * 2) + 1) % 1;
            var alpha = 50 + (int)(205 * Math.Pow(1 - distance, 3));
            using var pen = new Pen(Color.FromArgb(alpha, StatusColor), 3.4f);
            g.DrawArc(pen, ring, index * 20 - 90, 22);
        }

        var body = new RectangleF(8, 8, Width - 16, Height - 16);
        using (var fill = new System.Drawing.Drawing2D.LinearGradientBrush(body,
                   Color.FromArgb(69, 79, 220), Color.FromArgb(10, 160, 181), 55f))
            g.FillEllipse(fill, body);
        using (var outline = new Pen(Color.FromArgb(115, 255, 255, 255), 1.2f))
            g.DrawEllipse(outline, body);

        var points = new[] { new PointF(31, 43), new PointF(19, 22), new PointF(44, 25) };
        using (var link = new Pen(Color.FromArgb(225, 255, 255, 255), 2.1f))
        {
            g.DrawLine(link, points[0], points[1]);
            g.DrawLine(link, points[1], points[2]);
            g.DrawLine(link, points[2], points[0]);
        }
        for (var index = 0; index < points.Length; index++)
        {
            var pulse = Math.Max(0, Math.Sin(MotionPhase * 1.45 - index * 1.25));
            var haloRadius = 6f + (float)pulse * 4f;
            using var halo = new SolidBrush(Color.FromArgb((int)(pulse * 115), 137, 238, 255));
            g.FillEllipse(halo, points[index].X - haloRadius, points[index].Y - haloRadius, haloRadius * 2, haloRadius * 2);
            using var node = new SolidBrush(Color.White);
            g.FillEllipse(node, points[index].X - 4, points[index].Y - 4, 8, 8);
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        if (e.KeyCode is Keys.Enter or Keys.Space) { KeyboardActivate?.Invoke(this, EventArgs.Empty); e.Handled = true; }
        base.OnKeyDown(e);
    }
}

internal sealed class CompanionButtonForm : Form
{
    private const int ButtonSize = 62;
    private readonly string? uiStatePath;
    private readonly string? pidFilePath;
    private readonly string? controlFilePath;
    private readonly WorkbenchForm workbench;
    private readonly ResearchCompanionButton researchButton;
    private readonly System.Windows.Forms.Timer controlTimer;
    private readonly System.Windows.Forms.Timer motionTimer;
    private readonly System.Windows.Forms.Timer entranceTimer;
    private Point pointerStart;
    private Point formStart;
    private Point entranceTarget;
    private bool pointerDown;
    private bool dragged;
    private bool suppressClick;
    private int entranceFrame;
    private double motionPhase;
    private long controlVersion;
    private bool controlBusy;
    private string? lastControl;

    public CompanionButtonForm(string url, string title, string? uiState, string? pidFile, string? controlFile)
    {
        uiStatePath = uiState;
        pidFilePath = pidFile;
        controlFilePath = controlFile;

        Text = "Vibe Research 研究伴侣";
        AccessibleName = Text;

        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = true;
        TopMost = true;
        StartPosition = FormStartPosition.Manual;
        ClientSize = new Size(ButtonSize, ButtonSize);
        MinimumSize = MaximumSize = Size;
        BackColor = Color.Magenta;
        TransparencyKey = Color.Magenta;
        DoubleBuffered = true;
        Location = LoadButtonLocation() ?? DefaultButtonLocation(Screen.PrimaryScreen);

        researchButton = new ResearchCompanionButton
        {
            Bounds = new Rectangle(0, 0, ButtonSize, ButtonSize)
        };
        researchButton.MouseDown += BeginButtonGesture;
        researchButton.MouseMove += ContinueButtonGesture;
        researchButton.MouseUp += EndButtonGesture;
        researchButton.Click += ToggleFromClick;
        researchButton.KeyboardActivate += async (_, _) => await ToggleWorkbenchAsync();
        Controls.Add(researchButton);

        var menu = new ContextMenuStrip();
        menu.Items.Add("打开研究现场", null, async (_, _) => await ShowWorkbenchAsync());
        menu.Items.Add("重置入口位置", null, (_, _) => ResetPosition());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("退出研究伴侣", null, (_, _) => Close());
        researchButton.ContextMenuStrip = menu;

        workbench = new WorkbenchForm(url, title, () => HideWorkbench(), color =>
        {
            researchButton.StatusColor = color;
            researchButton.Invalidate();
            PersistState();
        });
        workbench.LocationChanged += (_, _) => PersistState();
        workbench.SizeChanged += (_, _) => PersistState();

        Move += (_, _) => PersistState();
        FormClosed += (_, _) => Cleanup();
        Shown += (_, _) =>
        {
            BeginEntrance();
            PersistState();
        };

        if (!string.IsNullOrWhiteSpace(pidFilePath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(pidFilePath)!);
            File.WriteAllText(pidFilePath, Environment.ProcessId + Environment.NewLine);
        }

        controlVersion = ReadControlVersion();
        controlTimer = new System.Windows.Forms.Timer { Interval = 400 };
        controlTimer.Tick += async (_, _) =>
        {
            if (!Screen.AllScreens.Any(s => s.WorkingArea.Contains(Bounds))) ResetPosition();
            if (controlBusy) return;
            var next = ReadControlVersion();
            if (next != 0 && next != controlVersion)
            {
                controlVersion = next;
                controlBusy = true;
                try
                {
                    var command = ReadControlCommand();
                    switch (command.Action)
                    {
                        case "show": await ShowWorkbenchAsync(); break;
                        case "hide": HideWorkbench(); break;
                        case "reset-position": ResetPosition(); break;
                        case "stop": lastControl = command.Id; PersistState(); Close(); return;
                        default: await ToggleWorkbenchAsync(); break;
                    }
                    lastControl = command.Id;
                    PersistState();
                }
                finally { controlBusy = false; }
            }
        };
        controlTimer.Start();

        motionTimer = new System.Windows.Forms.Timer { Interval = 50 };
        motionTimer.Tick += (_, _) =>
        {
            motionPhase = (motionPhase + .08) % (Math.PI * 2);
            researchButton.MotionPhase = motionPhase;
            researchButton.Invalidate();
        };
        if (SystemInformation.IsMenuAnimationEnabled) motionTimer.Start();

        entranceTimer = new System.Windows.Forms.Timer { Interval = 16 };
        entranceTimer.Tick += (_, _) =>
        {
            entranceFrame++;
            var progress = Math.Min(1d, entranceFrame / 28d);
            var eased = 1 - Math.Pow(1 - progress, 3);
            Opacity = eased;
            Location = new Point(entranceTarget.X, entranceTarget.Y + (int)Math.Round((1 - eased) * 12));
            if (progress < 1) return;
            entranceTimer.Stop();
            Opacity = 1;
            Location = entranceTarget;
        };
    }

    private void BeginEntrance()
    {
        if (!SystemInformation.IsMenuAnimationEnabled) return;
        entranceTarget = Location;
        entranceFrame = 0;
        Opacity = 0;
        Location = new Point(entranceTarget.X, entranceTarget.Y + 12);
        entranceTimer.Start();
    }

    private Point? LoadButtonLocation()
    {
        if (string.IsNullOrWhiteSpace(uiStatePath) || !File.Exists(uiStatePath)) return null;
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(uiStatePath));
            var root = document.RootElement;
            if (!root.TryGetProperty("button_x", out var xValue) || !root.TryGetProperty("button_y", out var yValue)) return null;
            var point = new Point((int)Math.Round(xValue.GetDouble()), (int)Math.Round(yValue.GetDouble()));
            return Screen.AllScreens.Any(screen => screen.WorkingArea.Contains(new Rectangle(point, Size)))
                ? point
                : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static Point DefaultButtonLocation(Screen? screen)
    {
        var area = (screen ?? Screen.PrimaryScreen)!.WorkingArea;
        return new Point(area.Right - ButtonSize - 18, area.Top + 18);
    }

    private void ResetPosition()
    {
        entranceTimer?.Stop();
        Opacity = 1;
        Location = DefaultButtonLocation(Screen.PrimaryScreen);
        PersistState();
    }

    private void BeginButtonGesture(object? sender, MouseEventArgs eventArgs)
    {
        if (eventArgs.Button != MouseButtons.Left) return;
        entranceTimer.Stop();
        Opacity = 1;
        suppressClick = false;
        pointerDown = true;
        dragged = false;
        pointerStart = researchButton.PointToScreen(eventArgs.Location);
        formStart = Location;
        researchButton.Capture = true;
    }

    private void ContinueButtonGesture(object? sender, MouseEventArgs eventArgs)
    {
        if (!pointerDown) return;
        var current = researchButton.PointToScreen(eventArgs.Location);
        var delta = new Size(current.X - pointerStart.X, current.Y - pointerStart.Y);
        if (Math.Abs(delta.Width) > 3 || Math.Abs(delta.Height) > 3) dragged = true;
        if (!dragged) return;

        var target = formStart + delta;
        var screen = Screen.FromPoint(current).WorkingArea;
        target.X = Math.Clamp(target.X, screen.Left, screen.Right - Width);
        target.Y = Math.Clamp(target.Y, screen.Top, screen.Bottom - Height);
        Location = target;
    }

    private void EndButtonGesture(object? sender, MouseEventArgs eventArgs)
    {
        if (eventArgs.Button != MouseButtons.Left) return;
        var current = researchButton.PointToScreen(eventArgs.Location);
        var delta = new Size(current.X - pointerStart.X, current.Y - pointerStart.Y);
        if (Math.Abs(delta.Width) > 3 || Math.Abs(delta.Height) > 3)
        {
            dragged = true;
            var area = Screen.FromPoint(current).WorkingArea;
            Location = new Point(Math.Clamp(formStart.X + delta.Width, area.Left, area.Right - Width),
                                 Math.Clamp(formStart.Y + delta.Height, area.Top, area.Bottom - Height));
        }
        pointerDown = false;
        researchButton.Capture = false;
        suppressClick = dragged;
        if (dragged) PersistState();
    }

    private async void ToggleFromClick(object? sender, EventArgs eventArgs)
    {
        if (dragged || suppressClick)
        {
            suppressClick = false;
            return;
        }
        await ToggleWorkbenchAsync();
    }

    private async Task ToggleWorkbenchAsync()
    {
        if (workbench.Visible) HideWorkbench();
        else await ShowWorkbenchAsync();
    }

    private async Task ShowWorkbenchAsync()
    {
        var targetScreen = Screen.FromControl(this);
        if (await workbench.ShowWorkbenchAsync(targetScreen))
            researchButton.AccessibleDescription = "收起 Vibe Research 研究现场；拖拽可移动入口";
        PersistState();
    }

    private void HideWorkbench()
    {
        workbench.Hide();
        researchButton.AccessibleDescription = "打开 Vibe Research 研究现场；拖拽可移动入口";
        PersistState();
    }

    private long ReadControlVersion()
    {
        if (string.IsNullOrWhiteSpace(controlFilePath) || !File.Exists(controlFilePath)) return 0;
        try { return File.GetLastWriteTimeUtc(controlFilePath).Ticks; }
        catch (IOException) { return 0; }
    }

    private (string Action, string? Id) ReadControlCommand()
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(controlFilePath!));
            var root = document.RootElement;
            if (root.ValueKind == JsonValueKind.Object)
                return (root.GetProperty("action").GetString() ?? "toggle", root.GetProperty("request_id").GetString());
        }
        catch (Exception) { }
        return ("toggle", null);
    }

    private void PersistState()
    {
        if (string.IsNullOrWhiteSpace(uiStatePath) || workbench is null) return;
        var payload = new
        {
            expanded = workbench.Visible,
            separate_windows = true,
            desktop = NativeMethods.DesktopName(),
            button_visible = Visible,
            last_control = lastControl,
            control_protocol = 1,
            navigation = workbench.NavigationStatus,
            navigation_error = workbench.NavigationError,
            button_x = Left,
            button_y = Top,
            button_width = Width,
            button_height = Height,
            panel_width = workbench.Width,
            panel_height = workbench.Height,
            content_width = workbench.ClientSize.Width,
            web_x = workbench.WebBounds.X,
            web_width = workbench.WebBounds.Width,
            web_height = workbench.WebBounds.Height,
            web_right_gap = Math.Max(0, workbench.ClientSize.Width - workbench.WebBounds.Right),
            updated_at = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
        };
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(uiStatePath)!);
            var temporary = uiStatePath + ".tmp";
            File.WriteAllText(temporary, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
            File.Move(temporary, uiStatePath, true);
        }
        catch (IOException) { }
    }

    private void Cleanup()
    {
        controlTimer.Stop();
        motionTimer.Stop();
        entranceTimer.Stop();
        workbench.CloseForExit();
        if (!string.IsNullOrWhiteSpace(pidFilePath))
        {
            try { File.Delete(pidFilePath); }
            catch (IOException) { }
        }
    }
}

internal sealed class WorkbenchForm : Form
{
    private const int HeaderHeight = 62;
    private readonly string url;
    private readonly Action collapse;
    private readonly Action<Color> statusChanged;
    private readonly WebView2 webView;
    private bool loaded;
    private bool exiting;

    public Rectangle WebBounds => webView.Bounds;
    public string NavigationStatus { get; private set; } = "not_loaded";
    public string? NavigationError { get; private set; }

    public WorkbenchForm(string workbenchUrl, string title, Action collapseAction, Action<Color> statusAction)
    {
        url = workbenchUrl;
        collapse = collapseAction;
        statusChanged = statusAction;
        Text = title;
        AccessibleName = title;
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = true;
        TopMost = true;
        StartPosition = FormStartPosition.Manual;
        BackColor = Color.FromArgb(239, 244, 252);
        ClientSize = new Size(1120, 780);
        MinimumSize = MaximumSize = Size;

        var header = new Panel { Dock = DockStyle.Top, Height = HeaderHeight, Padding = new Padding(12, 15, 18, 15), BackColor = Color.FromArgb(26, 36, 56) };
        header.MouseDown += DragHeader;
        var titleLabel = new Label
        {
            Text = title,
            AutoSize = true,
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 11, FontStyle.Bold),
            Location = new Point(20, 20)
        };
        titleLabel.MouseDown += DragHeader;
        var closeButton = new Button
        {
            Text = "收起",
            Size = new Size(62, 32),
            Dock = DockStyle.Right,
            FlatStyle = FlatStyle.Flat,
            ForeColor = Color.White,
            BackColor = Color.FromArgb(47, 68, 99),
            TabStop = false
        };
        closeButton.FlatAppearance.BorderColor = Color.FromArgb(100, 255, 255, 255);
        closeButton.Click += (_, _) => collapse();
        header.Controls.Add(titleLabel);
        header.Controls.Add(closeButton);

        var webHost = new Panel { Dock = DockStyle.Fill, Padding = new Padding(10), BackColor = Color.FromArgb(239, 244, 252) };
        webView = new WebView2 { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.FromArgb(239, 244, 252) };
        webHost.Controls.Add(webView);
        Controls.Add(webHost);
        Controls.Add(header);

        FormClosing += (_, eventArgs) =>
        {
            if (exiting) return;
            eventArgs.Cancel = true;
            collapse();
        };
    }

    public async Task<bool> ShowWorkbenchAsync(Screen screen)
    {
        var area = screen.WorkingArea;
        var width = Math.Min(1120, Math.Max(320, area.Width - 80));
        var height = Math.Min(780, Math.Max(320, area.Height - 80));
        MinimumSize = Size.Empty;
        MaximumSize = Size.Empty;
        Size = new Size(width, height);
        MinimumSize = MaximumSize = Size;
        Location = new Point(area.Left + (area.Width - width) / 2, area.Top + (area.Height - height) / 2);
        Show();
        BringToFront();
        Activate();
        try
        {
            if (!loaded)
            {
                statusChanged(Color.FromArgb(255, 171, 43));
                NavigationStatus = "loading";
                await webView.EnsureCoreWebView2Async();
                webView.CoreWebView2.NewWindowRequested += (_, eventArgs) =>
                {
                    eventArgs.Handled = true;
                    if (Uri.TryCreate(eventArgs.Uri, UriKind.Absolute, out var target) &&
                        (target.Scheme == Uri.UriSchemeHttp || target.Scheme == Uri.UriSchemeHttps))
                    {
                        Process.Start(new ProcessStartInfo(target.ToString()) { UseShellExecute = true });
                    }
                };
                webView.CoreWebView2.NavigationCompleted += (_, eventArgs) =>
                {
                    NavigationStatus = eventArgs.IsSuccess ? "ready" : "failed";
                    NavigationError = eventArgs.IsSuccess ? null : eventArgs.WebErrorStatus.ToString();
                    statusChanged(eventArgs.IsSuccess ? Color.FromArgb(31, 224, 150) : Color.FromArgb(244, 75, 86));
                };
                webView.Source = new Uri(url);
                loaded = true;
            }
            return true;
        }
        catch (Exception exception)
        {
            NavigationStatus = "failed";
            NavigationError = exception.Message;
            statusChanged(Color.FromArgb(244, 75, 86));
            Hide();
            MessageBox.Show(
                "研究现场未能启动。请确认 Microsoft Edge WebView2 Runtime 已安装，然后重试；浏览器入口 vr-workbench.cmd 仍可使用。",
                "Vibe Research",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return false;
        }
    }

    public void CloseForExit()
    {
        exiting = true;
        Close();
    }

    private void DragHeader(object? sender, MouseEventArgs eventArgs)
    {
        if (eventArgs.Button != MouseButtons.Left) return;
        NativeMethods.ReleaseCapture();
        NativeMethods.SendMessage(Handle, 0xA1, 0x2, 0);
    }
}

internal static class NativeMethods
{
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] private static extern IntPtr GetThreadDesktop(uint threadId);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern bool GetUserObjectInformation(IntPtr handle, int index, StringBuilder value, int length, out int needed);
    internal static string DesktopName()
    {
        var name = new StringBuilder(256);
        return GetUserObjectInformation(GetThreadDesktop(GetCurrentThreadId()), 2, name, 512, out _) ? name.ToString() : "unknown";
    }
    [DllImport("user32.dll")]
    internal static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    internal static extern IntPtr SendMessage(IntPtr window, int message, int parameter, int value);

}
