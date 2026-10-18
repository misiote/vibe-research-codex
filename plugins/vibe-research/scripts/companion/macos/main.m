#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <WebKit/WebKit.h>
#import <fcntl.h>
#import <signal.h>
#import <sys/file.h>
#import <unistd.h>

static int VRInstanceLockFD = -1;

static BOOL AcquireInstanceLock(NSString *pidFilePath) {
    if (!pidFilePath.length) return YES;
    NSString *lockPath = [pidFilePath stringByAppendingString:@".lock"];
    int fd = open(lockPath.fileSystemRepresentation, O_CREAT | O_RDWR, 0600);
    if (fd < 0) return NO;
    if (flock(fd, LOCK_EX | LOCK_NB) != 0) {
        close(fd);
        return NO;
    }
    VRInstanceLockFD = fd;
    return YES;
}

@interface VRInteractivePanel : NSPanel
@end

@implementation VRInteractivePanel
- (BOOL)canBecomeKeyWindow { return YES; }
- (BOOL)canBecomeMainWindow { return YES; }
@end

@interface VRDraggableHeaderView : NSView
@end

@implementation VRDraggableHeaderView
- (void)mouseDown:(NSEvent *)event {
    NSPoint startMouse = NSEvent.mouseLocation;
    NSPoint startOrigin = self.window.frame.origin;
    while (YES) {
        NSEvent *next = [self.window nextEventMatchingMask:NSEventMaskLeftMouseDragged | NSEventMaskLeftMouseUp];
        if (next.type == NSEventTypeLeftMouseDragged) {
            NSPoint current = NSEvent.mouseLocation;
            [self.window setFrameOrigin:NSMakePoint(startOrigin.x + current.x - startMouse.x,
                                                    startOrigin.y + current.y - startMouse.y)];
        } else if (next.type == NSEventTypeLeftMouseUp) {
            break;
        }
    }
}
@end

@interface VRInteractiveWebView : WKWebView
@end

@implementation VRInteractiveWebView
- (BOOL)acceptsFirstMouse:(NSEvent *)event { return YES; }
- (void)magnifyWithEvent:(NSEvent *)event {
    NSPoint local = [self convertPoint:event.locationInWindow fromView:nil];
    CGFloat webY = NSHeight(self.bounds) - local.y;
    NSString *phase = @"changed";
    if (event.phase == NSEventPhaseBegan || event.phase == NSEventPhaseMayBegin) phase = @"began";
    else if (event.phase == NSEventPhaseEnded) phase = @"ended";
    else if (event.phase == NSEventPhaseCancelled) phase = @"cancelled";
    NSString *script = [NSString stringWithFormat:
        @"(()=>{const x=%.3f,y=%.3f,p='%@',d=%.8f;let w=window,lx=x,ly=y;const el=document.elementFromPoint(x,y);if(el&&el.tagName==='IFRAME'&&el.contentWindow){const r=el.getBoundingClientRect();w=el.contentWindow;lx=x-r.left;ly=y-r.top;}const f=w.__vrNativeMagnify;return typeof f==='function'?f({phase:p,delta:d,x:lx,y:ly}):false;})()",
        local.x, webY, phase, event.magnification];
    [self evaluateJavaScript:script completionHandler:nil];
}
@end

@interface VRResearchButton : NSButton
@property(nonatomic) BOOL hovering;
@property(nonatomic, strong) NSTrackingArea *hoverArea;
@property(nonatomic, strong) NSArray<CAShapeLayer *> *nodeHalos;
@property(nonatomic, strong) CAShapeLayer *edgeTraveler;
@property(nonatomic, strong) NSImage *hostBadge;
@end

@implementation VRResearchButton
- (BOOL)isOpaque { return NO; }
- (void)updateTrackingAreas {
    [super updateTrackingAreas];
    if (self.hoverArea) [self removeTrackingArea:self.hoverArea];
    self.hoverArea = [[NSTrackingArea alloc] initWithRect:self.bounds
                                                  options:NSTrackingActiveAlways | NSTrackingMouseEnteredAndExited | NSTrackingInVisibleRect
                                                    owner:self
                                                 userInfo:nil];
    [self addTrackingArea:self.hoverArea];
}
- (void)mouseEntered:(NSEvent *)event { self.hovering = YES; self.alphaValue = 1.0; self.needsDisplay = YES; }
- (void)mouseExited:(NSEvent *)event { self.hovering = NO; self.alphaValue = 0.94; self.needsDisplay = YES; }
- (void)mouseDown:(NSEvent *)event {
    NSPoint startMouse = NSEvent.mouseLocation;
    NSPoint startOrigin = self.window.frame.origin;
    BOOL dragged = NO;
    while (YES) {
        NSEvent *next = [self.window nextEventMatchingMask:NSEventMaskLeftMouseDragged | NSEventMaskLeftMouseUp];
        if (next.type == NSEventTypeLeftMouseDragged) {
            NSPoint current = NSEvent.mouseLocation;
            CGFloat dx = current.x - startMouse.x;
            CGFloat dy = current.y - startMouse.y;
            if (hypot(dx, dy) > 3) dragged = YES;
            if (dragged) [self.window setFrameOrigin:NSMakePoint(startOrigin.x + dx, startOrigin.y + dy)];
        } else if (next.type == NSEventTypeLeftMouseUp) {
            if (!dragged) [NSApp sendAction:self.action to:self.target from:self];
            break;
        }
    }
}
- (void)rightMouseDown:(NSEvent *)event {
    if (self.menu) [NSMenu popUpContextMenu:self.menu withEvent:event forView:self];
}
- (void)drawRect:(NSRect)dirtyRect {
    [[NSColor clearColor] setFill];
    NSRectFillUsingOperation(self.bounds, NSCompositingOperationCopy);
    NSRect box = NSInsetRect(self.bounds, 7, 7);
    NSBezierPath *shape = [NSBezierPath bezierPathWithOvalInRect:box];
    NSColor *top = self.hovering
        ? [NSColor colorWithCalibratedRed:.34 green:.42 blue:.98 alpha:1]
        : [NSColor colorWithCalibratedRed:.27 green:.32 blue:.86 alpha:1];
    NSColor *bottom = [NSColor colorWithCalibratedRed:.04 green:.62 blue:.70 alpha:1];
    [NSGraphicsContext saveGraphicsState];
    NSShadow *shadow = [[NSShadow alloc] init];
    shadow.shadowColor = [NSColor colorWithWhite:0 alpha:.28];
    shadow.shadowBlurRadius = 5;
    shadow.shadowOffset = NSMakeSize(0, -1);
    [shadow set];
    [[[NSGradient alloc] initWithStartingColor:top endingColor:bottom] drawInBezierPath:shape angle:-55];
    [NSGraphicsContext restoreGraphicsState];
    [[NSColor colorWithWhite:1 alpha:.34] setStroke];
    shape.lineWidth = 1.2;
    [shape stroke];

    [[NSColor colorWithWhite:1 alpha:.88] setStroke];
    NSBezierPath *links = [NSBezierPath bezierPath];
    links.lineWidth = 2.1;
    [links moveToPoint:NSMakePoint(NSMidX(self.bounds), NSMidY(self.bounds) + 12)];
    [links lineToPoint:NSMakePoint(NSMidX(self.bounds) - 12, NSMidY(self.bounds) - 9)];
    [links lineToPoint:NSMakePoint(NSMidX(self.bounds) + 13, NSMidY(self.bounds) - 6)];
    [links closePath];
    [links stroke];
    NSArray<NSValue *> *points = @[
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.bounds), NSMidY(self.bounds) + 12)],
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.bounds) - 12, NSMidY(self.bounds) - 9)],
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.bounds) + 13, NSMidY(self.bounds) - 6)]
    ];
    [[NSColor whiteColor] setFill];
    for (NSValue *value in points) {
        NSPoint point = value.pointValue;
        [[NSBezierPath bezierPathWithOvalInRect:NSMakeRect(point.x - 4, point.y - 4, 8, 8)] fill];
    }

    if (!self.hostBadge) {
        NSString *badgePath = [NSBundle.mainBundle pathForResource:@"host-badge" ofType:@"png"];
        if (badgePath.length) self.hostBadge = [[NSImage alloc] initWithContentsOfFile:badgePath];
    }
    if (self.hostBadge) {
        NSRect badgeFrame = NSMakeRect(NSMaxX(self.bounds) - 24, 4, 20, 20);
        NSRect imageFrame = NSInsetRect(badgeFrame, 2.2, 2.2);
        NSBezierPath *backing = [NSBezierPath bezierPathWithRoundedRect:badgeFrame xRadius:6.5 yRadius:6.5];
        [NSGraphicsContext saveGraphicsState];
        NSShadow *badgeShadow = [[NSShadow alloc] init];
        badgeShadow.shadowColor = [NSColor colorWithWhite:0 alpha:.32];
        badgeShadow.shadowBlurRadius = 2.5;
        badgeShadow.shadowOffset = NSMakeSize(0, -1);
        [badgeShadow set];
        [[NSColor colorWithWhite:.98 alpha:.96] setFill];
        [backing fill];
        [NSGraphicsContext restoreGraphicsState];

        [NSGraphicsContext saveGraphicsState];
        [[NSBezierPath bezierPathWithRoundedRect:imageFrame xRadius:4.6 yRadius:4.6] addClip];
        [self.hostBadge drawInRect:imageFrame
                          fromRect:NSZeroRect
                         operation:NSCompositingOperationSourceOver
                          fraction:1.0
                    respectFlipped:YES
                             hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];
        [NSGraphicsContext restoreGraphicsState];
        [[NSColor colorWithWhite:1 alpha:.72] setStroke];
        backing.lineWidth = .8;
        [backing stroke];
    }
}
@end

@interface VRCompanionController : NSObject <NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate>
@property(nonatomic, strong) NSURL *url;
@property(nonatomic, copy) NSString *titleText;
@property(nonatomic, strong) NSPanel *buttonPanel;
@property(nonatomic, strong) NSPanel *workbenchPanel;
@property(nonatomic, strong) WKWebView *webView;
@property(nonatomic, strong) VRDraggableHeaderView *headerView;
@property(nonatomic, strong) NSTextField *titleLabel;
@property(nonatomic, strong) CAGradientLayer *statusRing;
@property(nonatomic, strong) VRResearchButton *toggleButton;
@property(nonatomic, strong) NSButton *closeButton;
@property(nonatomic) BOOL expanded;
@property(nonatomic) BOOL loaded;
@property(nonatomic, strong) NSTimer *visibilityTimer;
@property(nonatomic, copy) NSString *uiStatePath;
@property(nonatomic, copy) NSString *pidFilePath;
@property(nonatomic, strong) dispatch_source_t toggleSignal;
@property(nonatomic, strong) NSDictionary *domMetrics;
@property(nonatomic) BOOL hasPresentedEntrance;
@property(nonatomic) BOOL reduceMotion;
@end

@implementation VRCompanionController
- (instancetype)initWithURL:(NSURL *)url title:(NSString *)title uiStatePath:(NSString *)uiStatePath pidFilePath:(NSString *)pidFilePath {
    if ((self = [super init])) {
        _url = url;
        _titleText = [title copy];
        _uiStatePath = [uiStatePath copy];
        _pidFilePath = [pidFilePath copy];
    }
    return self;
}
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
    for (NSRunningApplication *candidate in NSWorkspace.sharedWorkspace.runningApplications) {
        if (candidate.processIdentifier == NSProcessInfo.processInfo.processIdentifier) continue;
        NSString *executable = candidate.executableURL.lastPathComponent.lowercaseString;
        if ([executable isEqualToString:@"vr-companion"]) {
            if (![candidate terminate]) kill(candidate.processIdentifier, SIGTERM);
        }
    }
    if (self.pidFilePath.length) {
        NSString *pid = [NSString stringWithFormat:@"%d\n", NSProcessInfo.processInfo.processIdentifier];
        [pid writeToFile:self.pidFilePath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
    [self buildPanels];
    self.reduceMotion = NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion;
    [self configureButtonMotion];
    [self showCollapsed];
    signal(SIGUSR1, SIG_IGN);
    self.toggleSignal = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGUSR1, 0, dispatch_get_main_queue());
    __weak VRCompanionController *weakSelf = self;
    dispatch_source_set_event_handler(self.toggleSignal, ^{ [weakSelf toggleWorkbench:nil]; });
    dispatch_resume(self.toggleSignal);
    self.visibilityTimer = [NSTimer scheduledTimerWithTimeInterval:.7
                                                           target:self
                                                         selector:@selector(syncVisibility:)
                                                         userInfo:nil
                                                          repeats:YES];
}
- (void)applicationWillTerminate:(NSNotification *)notification {
    if (self.pidFilePath.length) [NSFileManager.defaultManager removeItemAtPath:self.pidFilePath error:nil];
}
- (NSDictionary *)savedUIState {
    if (!self.uiStatePath.length) return @{};
    NSData *data = [NSData dataWithContentsOfFile:self.uiStatePath];
    if (!data) return @{};
    id object = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    return [object isKindOfClass:NSDictionary.class] ? object : @{};
}
- (NSPoint)initialButtonOrigin {
    NSRect visible = NSScreen.mainScreen.visibleFrame;
    if (NSIsEmptyRect(visible)) visible = NSMakeRect(0, 0, 1440, 900);
    NSPoint fallback = NSMakePoint(NSMaxX(visible) - 80, NSMaxY(visible) - 80);
    NSDictionary *saved = [self savedUIState];
    NSNumber *x = saved[@"button_x"];
    NSNumber *y = saved[@"button_y"];
    if (!x || !y) return fallback;
    NSPoint point = NSMakePoint(x.doubleValue, y.doubleValue);
    for (NSScreen *screen in NSScreen.screens) {
        NSRect allowed = NSInsetRect(screen.visibleFrame, -31, -31);
        if (NSPointInRect(NSMakePoint(point.x + 31, point.y + 31), allowed)) return point;
    }
    return fallback;
}
- (NSVisualEffectView *)rootViewWithFrame:(NSRect)frame radius:(CGFloat)radius {
    NSVisualEffectView *root = [[NSVisualEffectView alloc] initWithFrame:frame];
    root.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    root.material = NSVisualEffectMaterialHUDWindow;
    root.blendingMode = NSVisualEffectBlendingModeBehindWindow;
    root.state = NSVisualEffectStateActive;
    root.wantsLayer = YES;
    root.layer.cornerRadius = radius;
    root.layer.masksToBounds = YES;
    return root;
}
- (NSView *)transparentRootViewWithFrame:(NSRect)frame {
    NSView *root = [[NSView alloc] initWithFrame:frame];
    root.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    root.wantsLayer = YES;
    root.layer.backgroundColor = NSColor.clearColor.CGColor;
    return root;
}
- (void)configurePanel:(NSPanel *)panel level:(NSInteger)level {
    panel.level = level;
    panel.floatingPanel = YES;
    panel.hidesOnDeactivate = NO;
    panel.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary;
    panel.backgroundColor = NSColor.clearColor;
    panel.opaque = NO;
    panel.hasShadow = YES;
    panel.delegate = self;
}
- (void)buildPanels {
    NSPoint origin = [self initialButtonOrigin];
    self.buttonPanel = [[NSPanel alloc] initWithContentRect:NSMakeRect(origin.x, origin.y, 62, 62)
                                                 styleMask:NSWindowStyleMaskBorderless | NSWindowStyleMaskFullSizeContentView
                                                   backing:NSBackingStoreBuffered
                                                     defer:NO];
    [self configurePanel:self.buttonPanel level:NSFloatingWindowLevel + 1];
    self.buttonPanel.hasShadow = NO;
    NSView *buttonRoot = [self transparentRootViewWithFrame:NSMakeRect(0, 0, 62, 62)];
    self.buttonPanel.contentView = buttonRoot;

    self.toggleButton = [[VRResearchButton alloc] initWithFrame:NSMakeRect(0, 0, 62, 62)];
    self.toggleButton.bordered = NO;
    self.toggleButton.alphaValue = 1;
    self.toggleButton.wantsLayer = YES;
    self.toggleButton.toolTip = @"Vibe Research · 点击打开，拖拽移动";
    self.toggleButton.target = self;
    self.toggleButton.action = @selector(toggleWorkbench:);
    [buttonRoot addSubview:self.toggleButton];

    NSMenu *menu = [[NSMenu alloc] init];
    NSMenuItem *open = [[NSMenuItem alloc] initWithTitle:@"打开研究现场" action:@selector(expandFromMenu:) keyEquivalent:@""];
    open.target = self;
    [menu addItem:open];
    [menu addItem:NSMenuItem.separatorItem];
    NSMenuItem *quit = [[NSMenuItem alloc] initWithTitle:@"退出研究伴侣" action:@selector(quitCompanion:) keyEquivalent:@""];
    quit.target = self;
    [menu addItem:quit];
    self.toggleButton.menu = menu;

    NSRect frame = [self expandedFrame];
    self.workbenchPanel = [[VRInteractivePanel alloc] initWithContentRect:frame
                                                   styleMask:NSWindowStyleMaskBorderless | NSWindowStyleMaskFullSizeContentView
                                                     backing:NSBackingStoreBuffered
                                                       defer:NO];
    [self configurePanel:self.workbenchPanel level:NSFloatingWindowLevel];
    self.workbenchPanel.movableByWindowBackground = NO;
    self.workbenchPanel.acceptsMouseMovedEvents = YES;
    self.workbenchPanel.becomesKeyOnlyIfNeeded = NO;
    NSVisualEffectView *workbenchRoot = [self rootViewWithFrame:NSMakeRect(0, 0, frame.size.width, frame.size.height) radius:20];
    self.workbenchPanel.contentView = workbenchRoot;

    self.headerView = [[VRDraggableHeaderView alloc] initWithFrame:NSMakeRect(0, frame.size.height - 66, frame.size.width, 66)];
    [workbenchRoot addSubview:self.headerView];

    self.titleLabel = [NSTextField labelWithString:self.titleText];
    self.titleLabel.font = [NSFont systemFontOfSize:15 weight:NSFontWeightSemibold];
    self.titleLabel.textColor = NSColor.labelColor;
    [workbenchRoot addSubview:self.titleLabel];

    self.closeButton = [NSButton buttonWithTitle:@"收起" target:self action:@selector(showCollapsed)];
    self.closeButton.bezelStyle = NSBezelStyleRounded;
    self.closeButton.font = [NSFont systemFontOfSize:13 weight:NSFontWeightMedium];
    [workbenchRoot addSubview:self.closeButton];

    WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
    configuration.websiteDataStore = WKWebsiteDataStore.defaultDataStore;
    self.webView = [[VRInteractiveWebView alloc] initWithFrame:NSMakeRect(10, 10, frame.size.width - 20, frame.size.height - 76)
                                      configuration:configuration];
    self.webView.navigationDelegate = self;
    self.webView.UIDelegate = self;
    self.webView.allowsMagnification = NO;
    self.webView.wantsLayer = YES;
    self.webView.layer.cornerRadius = 14;
    self.webView.layer.masksToBounds = YES;
    [workbenchRoot addSubview:self.webView];
    [self layoutWorkbench];
}
- (void)configureButtonMotion {
    CAGradientLayer *ring = [CAGradientLayer layer];
    ring.frame = self.toggleButton.bounds;
    ring.type = kCAGradientLayerConic;
    ring.startPoint = CGPointMake(.5, .5);
    ring.endPoint = CGPointMake(.5, 0);
    CAShapeLayer *ringMask = [CAShapeLayer layer];
    ringMask.frame = ring.bounds;
    CGPathRef ringPath = CGPathCreateWithEllipseInRect(CGRectInset(ring.bounds, 2.5, 2.5), NULL);
    ringMask.path = ringPath;
    CGPathRelease(ringPath);
    ringMask.fillColor = NSColor.clearColor.CGColor;
    ringMask.strokeColor = NSColor.whiteColor.CGColor;
    ringMask.lineWidth = 3.5;
    ring.mask = ringMask;
    [self.toggleButton.layer addSublayer:ring];
    self.statusRing = ring;
    [self setStatusRingColor:[NSColor colorWithCalibratedRed:.12 green:.88 blue:.59 alpha:1]];

    NSArray<NSValue *> *nodePoints = @[
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.toggleButton.bounds), NSMidY(self.toggleButton.bounds) + 12)],
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.toggleButton.bounds) - 12, NSMidY(self.toggleButton.bounds) - 9)],
        [NSValue valueWithPoint:NSMakePoint(NSMidX(self.toggleButton.bounds) + 13, NSMidY(self.toggleButton.bounds) - 6)]
    ];
    NSMutableArray<CAShapeLayer *> *halos = [NSMutableArray array];
    for (NSValue *value in nodePoints) {
        NSPoint point = value.pointValue;
        CAShapeLayer *halo = [CAShapeLayer layer];
        halo.frame = CGRectMake(point.x - 9, point.y - 9, 18, 18);
        CGPathRef haloPath = CGPathCreateWithEllipseInRect(halo.bounds, NULL);
        halo.path = haloPath;
        CGPathRelease(haloPath);
        halo.fillColor = [NSColor colorWithCalibratedRed:.54 green:.93 blue:1 alpha:.42].CGColor;
        halo.shadowColor = [NSColor colorWithCalibratedRed:.42 green:.9 blue:1 alpha:1].CGColor;
        halo.shadowOpacity = .92;
        halo.shadowRadius = 5;
        halo.shadowOffset = CGSizeZero;
        halo.opacity = 0;
        [self.toggleButton.layer addSublayer:halo];
        [halos addObject:halo];
    }
    self.toggleButton.nodeHalos = halos;

    CAShapeLayer *traveler = [CAShapeLayer layer];
    traveler.bounds = CGRectMake(0, 0, 5, 5);
    traveler.position = nodePoints.firstObject.pointValue;
    traveler.cornerRadius = 2.5;
    traveler.backgroundColor = [NSColor colorWithCalibratedRed:.76 green:.97 blue:1 alpha:1].CGColor;
    traveler.shadowColor = [NSColor whiteColor].CGColor;
    traveler.shadowOpacity = .9;
    traveler.shadowRadius = 4;
    traveler.shadowOffset = CGSizeZero;
    traveler.opacity = 0;
    [self.toggleButton.layer addSublayer:traveler];
    self.toggleButton.edgeTraveler = traveler;
    if (self.reduceMotion) return;

    CGMutablePathRef edgePath = CGPathCreateMutable();
    NSPoint top = nodePoints[0].pointValue;
    NSPoint left = nodePoints[1].pointValue;
    NSPoint right = nodePoints[2].pointValue;
    CGPathMoveToPoint(edgePath, NULL, top.x, top.y);
    CGPathAddLineToPoint(edgePath, NULL, left.x, left.y);
    CGPathAddLineToPoint(edgePath, NULL, right.x, right.y);
    CGPathAddLineToPoint(edgePath, NULL, top.x, top.y);
    CAKeyframeAnimation *edgeFlow = [CAKeyframeAnimation animationWithKeyPath:@"position"];
    edgeFlow.path = edgePath;
    edgeFlow.calculationMode = kCAAnimationPaced;
    CGPathRelease(edgePath);
    CAKeyframeAnimation *edgeOpacity = [CAKeyframeAnimation animationWithKeyPath:@"opacity"];
    edgeOpacity.values = @[@0, @1, @.9, @1, @0];
    edgeOpacity.keyTimes = @[@0, @.12, @.5, @.88, @1];
    CAAnimationGroup *flow = [CAAnimationGroup animation];
    flow.animations = @[edgeFlow, edgeOpacity];
    flow.duration = 4.8;
    flow.repeatCount = HUGE_VALF;
    flow.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [traveler addAnimation:flow forKey:@"vr.edgeFlow"];

    CABasicAnimation *breath = [CABasicAnimation animationWithKeyPath:@"transform.scale"];
    breath.fromValue = @.996;
    breath.toValue = @1.006;
    breath.duration = 3.8;
    breath.autoreverses = YES;
    breath.repeatCount = HUGE_VALF;
    breath.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [self.toggleButton.layer addAnimation:breath forKey:@"vr.breath"];

    CFTimeInterval now = CACurrentMediaTime();
    for (NSUInteger index = 0; index < halos.count; index++) {
        CAShapeLayer *halo = halos[index];
        CAKeyframeAnimation *pulseOpacity = [CAKeyframeAnimation animationWithKeyPath:@"opacity"];
        pulseOpacity.values = @[@0, @0, @1, @.3, @0];
        pulseOpacity.keyTimes = @[@0, @.2, @.34, @.55, @1];
        CAKeyframeAnimation *pulseScale = [CAKeyframeAnimation animationWithKeyPath:@"transform.scale"];
        pulseScale.values = @[@.72, @.72, @1.18, @1, @.86];
        pulseScale.keyTimes = pulseOpacity.keyTimes;
        CAAnimationGroup *pulse = [CAAnimationGroup animation];
        pulse.animations = @[pulseOpacity, pulseScale];
        pulse.duration = 3.6;
        pulse.beginTime = now + index * .42;
        pulse.repeatCount = HUGE_VALF;
        pulse.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
        [halo addAnimation:pulse forKey:@"vr.nodePulse"];
    }

    CABasicAnimation *ringFlow = [CABasicAnimation animationWithKeyPath:@"transform.rotation.z"];
    ringFlow.fromValue = @0;
    ringFlow.toValue = @(M_PI * 2);
    ringFlow.duration = 3.4;
    ringFlow.repeatCount = HUGE_VALF;
    ringFlow.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionLinear];
    [ring addAnimation:ringFlow forKey:@"vr.ringFlow"];
}
- (void)setStatusRingColor:(NSColor *)color {
    if (!self.statusRing) return;
    self.statusRing.colors = @[
        (id)[color colorWithAlphaComponent:.16].CGColor,
        (id)[color colorWithAlphaComponent:.48].CGColor,
        (id)[color colorWithAlphaComponent:1].CGColor,
        (id)[NSColor colorWithWhite:1 alpha:.92].CGColor,
        (id)[color colorWithAlphaComponent:.7].CGColor,
        (id)[color colorWithAlphaComponent:.16].CGColor
    ];
    self.statusRing.locations = @[@0, @.2, @.43, @.51, @.68, @1];
}
- (void)presentButtonWithEntranceIfNeeded {
    if (self.hasPresentedEntrance || self.reduceMotion) {
        self.buttonPanel.alphaValue = 1;
        [self.buttonPanel orderFrontRegardless];
        self.hasPresentedEntrance = YES;
        return;
    }
    self.hasPresentedEntrance = YES;
    NSPoint destination = self.buttonPanel.frame.origin;
    [self.buttonPanel setFrameOrigin:NSMakePoint(destination.x, destination.y - 12)];
    self.buttonPanel.alphaValue = 0;
    [self.buttonPanel orderFrontRegardless];
    self.toggleButton.layer.transform = CATransform3DMakeScale(.74, .74, 1);
    CASpringAnimation *arrival = [CASpringAnimation animationWithKeyPath:@"transform.scale"];
    arrival.fromValue = @.74;
    arrival.toValue = @1;
    arrival.mass = .8;
    arrival.stiffness = 175;
    arrival.damping = 15;
    arrival.initialVelocity = .2;
    arrival.duration = MIN(.72, arrival.settlingDuration);
    self.toggleButton.layer.transform = CATransform3DIdentity;
    [self.toggleButton.layer addAnimation:arrival forKey:@"vr.arrival"];
    [NSAnimationContext runAnimationGroup:^(NSAnimationContext *context) {
        context.duration = .44;
        context.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseOut];
        self.buttonPanel.animator.alphaValue = 1;
        [self.buttonPanel.animator setFrameOrigin:destination];
    } completionHandler:nil];
}
- (NSRect)expandedFrame {
    NSScreen *targetScreen = self.buttonPanel.screen ?: NSScreen.mainScreen;
    NSRect screen = targetScreen.visibleFrame;
    if (NSIsEmptyRect(screen)) screen = NSScreen.mainScreen.visibleFrame;
    CGFloat width = MIN(1120, MAX(760, screen.size.width - 120));
    CGFloat height = MIN(780, MAX(560, screen.size.height - 100));
    return NSMakeRect(NSMidX(screen) - width / 2, NSMidY(screen) - height / 2, width, height);
}
- (void)layoutWorkbench {
    NSRect bounds = self.workbenchPanel.contentView.bounds;
    CGFloat width = NSWidth(bounds);
    CGFloat height = NSHeight(bounds);
    self.titleLabel.frame = NSMakeRect(22, height - 43, MAX(1, width - 120), 24);
    self.closeButton.frame = NSMakeRect(width - 76, height - 48, 58, 30);
    self.headerView.frame = NSMakeRect(0, height - 66, width, 66);
    self.webView.frame = NSMakeRect(10, 10, MAX(1, width - 20), MAX(1, height - 76));
    [self.workbenchPanel.contentView layoutSubtreeIfNeeded];
}
- (void)refreshWebLayout {
    if (!self.loaded || !self.expanded) return;
    self.webView.pageZoom = 1.0;
    CGFloat nativeWidth = NSWidth(self.webView.bounds);
    NSString *layout = [NSString stringWithFormat:@"(()=>{let s=document.getElementById('__vr_native_viewport');if(!s){s=document.createElement('style');s.id='__vr_native_viewport';document.head.appendChild(s);}s.textContent='html,body{width:%.0fpx!important;max-width:%.0fpx!important;overflow-x:hidden!important}';window.scrollTo(0,window.scrollY);window.dispatchEvent(new Event('resize'));})()", nativeWidth, nativeWidth];
    NSString *probe = @"(()=>{const m=document.querySelector('main');const r=m?m.getBoundingClientRect():null;return {inner_width:window.innerWidth,visual_width:window.visualViewport?window.visualViewport.width:0,doc_width:document.documentElement.clientWidth,body_width:document.body?document.body.clientWidth:0,scroll_width:document.documentElement.scrollWidth,main_x:r?r.x:0,main_width:r?r.width:0,dpr:window.devicePixelRatio||1};})()";
    __weak VRCompanionController *weakSelf = self;
    [self.webView evaluateJavaScript:layout completionHandler:^(id ignored, NSError *layoutError) {
        if (layoutError) return;
        [weakSelf.webView evaluateJavaScript:probe completionHandler:^(id result, NSError *error) {
            if (!error && [result isKindOfClass:NSDictionary.class]) {
                weakSelf.domMetrics = result;
                [weakSelf persistUIState];
            }
        }];
    }];
}
- (void)showCollapsed {
    self.expanded = NO;
    [self.workbenchPanel orderOut:nil];
    self.toggleButton.toolTip = @"Vibe Research · 点击打开，拖拽移动";
    [self presentButtonWithEntranceIfNeeded];
    [self persistUIState];
}
- (void)showExpanded {
    self.expanded = YES;
    [self.workbenchPanel setFrame:[self expandedFrame] display:YES animate:NO];
    [self layoutWorkbench];
    if (!self.loaded) {
        [self setStatusRingColor:NSColor.systemOrangeColor];
        self.webView.pageZoom = 1.0;
        self.loaded = YES;
        [self.webView loadRequest:[NSURLRequest requestWithURL:self.url]];
    }
    self.toggleButton.toolTip = @"Vibe Research · 点击收起，拖拽移动";
    [NSApp activateIgnoringOtherApps:YES];
    if (!self.reduceMotion) self.workbenchPanel.alphaValue = 0;
    [self.workbenchPanel makeKeyAndOrderFront:nil];
    if (!self.reduceMotion) {
        [NSAnimationContext runAnimationGroup:^(NSAnimationContext *context) {
            context.duration = .24;
            context.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseOut];
            self.workbenchPanel.animator.alphaValue = 1;
        } completionHandler:nil];
    }
    [self.workbenchPanel makeFirstResponder:self.webView];
    [self.buttonPanel orderFrontRegardless];
    dispatch_async(dispatch_get_main_queue(), ^{ [self refreshWebLayout]; });
    [self persistUIState];
}
- (void)toggleWorkbench:(id)sender { self.expanded ? [self showCollapsed] : [self showExpanded]; }
- (void)expandFromMenu:(id)sender { if (!self.expanded) [self showExpanded]; }
- (void)quitCompanion:(id)sender { [NSApp terminate:nil]; }
- (void)windowDidResize:(NSNotification *)notification {
    if (notification.object == self.workbenchPanel) {
        [self layoutWorkbench];
        [self refreshWebLayout];
    }
}
- (void)windowDidMove:(NSNotification *)notification {
    if (notification.object == self.buttonPanel) [self persistUIState];
}
- (void)persistUIState {
    if (!self.uiStatePath.length || !self.buttonPanel || !self.workbenchPanel) return;
    NSRect button = self.buttonPanel.frame;
    NSRect workbench = self.workbenchPanel.frame;
    NSMutableDictionary *payload = [@{
        @"expanded": @(self.expanded),
        @"separate_windows": @YES,
        @"button_x": @(button.origin.x),
        @"button_y": @(button.origin.y),
        @"button_width": @(button.size.width),
        @"button_height": @(button.size.height),
        @"panel_width": @(workbench.size.width),
        @"panel_height": @(workbench.size.height),
        @"content_width": @(self.workbenchPanel.contentView.bounds.size.width),
        @"web_x": @(self.webView.frame.origin.x),
        @"web_width": @(self.webView.frame.size.width),
        @"web_height": @(self.webView.frame.size.height),
        @"web_right_gap": @(self.workbenchPanel.contentView.bounds.size.width - NSMaxX(self.webView.frame)),
        @"updated_at": @((long long)[NSDate.date timeIntervalSince1970])
    } mutableCopy];
    if (self.domMetrics) payload[@"dom_metrics"] = self.domMetrics;
    NSData *data = [NSJSONSerialization dataWithJSONObject:payload options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:self.uiStatePath options:NSDataWritingAtomic error:nil];
}
- (void)syncVisibility:(NSTimer *)timer {
    NSRunningApplication *front = NSWorkspace.sharedWorkspace.frontmostApplication;
    BOOL belongsToCodex = [front.bundleIdentifier isEqualToString:@"com.openai.codex"];
    BOOL belongsToCompanion = front.processIdentifier == NSProcessInfo.processInfo.processIdentifier;
    if (belongsToCodex || belongsToCompanion) {
        if (!self.buttonPanel.visible) [self.buttonPanel orderFrontRegardless];
        if (self.expanded && !self.workbenchPanel.visible) [self.workbenchPanel orderFrontRegardless];
    } else {
        if (self.buttonPanel.visible) [self.buttonPanel orderOut:nil];
        if (self.workbenchPanel.visible) [self.workbenchPanel orderOut:nil];
    }
}
- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    [self setStatusRingColor:[NSColor colorWithCalibratedRed:.12 green:.88 blue:.59 alpha:1]];
    [self refreshWebLayout];
}
- (void)webView:(WKWebView *)webView didFailNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    [self setStatusRingColor:NSColor.systemRedColor];
}
- (void)webView:(WKWebView *)webView didFailProvisionalNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    [self setStatusRingColor:NSColor.systemRedColor];
}
- (WKWebView *)webView:(WKWebView *)webView
createWebViewWithConfiguration:(WKWebViewConfiguration *)configuration
   forNavigationAction:(WKNavigationAction *)navigationAction
        windowFeatures:(WKWindowFeatures *)windowFeatures {
    NSURL *target = navigationAction.request.URL;
    NSString *scheme = target.scheme.lowercaseString;
    if (target && ([scheme isEqualToString:@"http"] || [scheme isEqualToString:@"https"])) {
        [NSWorkspace.sharedWorkspace openURL:target];
    }
    return nil;
}
@end

static NSString *ArgumentValue(NSArray<NSString *> *arguments, NSString *flag) {
    NSUInteger index = [arguments indexOfObject:flag];
    return index != NSNotFound && index + 1 < arguments.count ? arguments[index + 1] : nil;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSArray<NSString *> *arguments = NSProcessInfo.processInfo.arguments;
        NSString *rawURL = ArgumentValue(arguments, @"--url");
        NSURL *url = rawURL ? [NSURL URLWithString:rawURL] : nil;
        if (!url) { fprintf(stderr, "missing --url\n"); return 2; }
        NSString *title = ArgumentValue(arguments, @"--title") ?: @"Vibe Research · 研究现场";
        NSString *uiStatePath = ArgumentValue(arguments, @"--ui-state");
        NSString *pidFilePath = ArgumentValue(arguments, @"--pid-file");
        if (!AcquireInstanceLock(pidFilePath)) return 0;
        NSApplication *app = NSApplication.sharedApplication;
        VRCompanionController *controller = [[VRCompanionController alloc] initWithURL:url title:title uiStatePath:uiStatePath pidFilePath:pidFilePath];
        app.delegate = controller;
        [app run];
    }
    return 0;
}
