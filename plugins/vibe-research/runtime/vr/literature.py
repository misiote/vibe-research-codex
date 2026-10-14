"""Public academic APIs. No paid provider or automatic billing upgrade."""
import hashlib
import math
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from .connections import credential
from .store import ResearchError, dumps, now

PROVIDERS = ("openalex", "s2", "arxiv", "crossref", "core", "huggingface", "wos", "scopus")
RESOLVERS = ("unpaywall",)
ALL_SOURCES = PROVIDERS + RESOLVERS
COVERAGE_PROVIDERS = ("openalex", "s2", "arxiv", "crossref", "core", "wos", "scopus")
FIELDS = "paperId,title,abstract,year,authors,externalIds,url,openAccessPdf"


def abstract(index):
    if not index:
        return None
    words = {position: word for word, positions in index.items() for position in positions}
    return " ".join(words[p] for p in sorted(words))


def normalize(provider, raw):
    if provider == "openalex":
        loc = raw.get("best_oa_location") or {}
        return {"provider": provider, "external_id": raw["id"], "title": raw.get("display_name") or "Untitled",
                "doi": raw.get("doi"), "year": raw.get("publication_year"),
                "authors": [a["author"]["display_name"] for a in raw.get("authorships", [])],
                "abstract": abstract(raw.get("abstract_inverted_index")), "url": raw["id"], "pdf_url": loc.get("pdf_url")}
    return {"provider": provider, "external_id": raw["paperId"], "title": raw.get("title") or "Untitled",
            "doi": (raw.get("externalIds") or {}).get("DOI"), "arxiv": (raw.get("externalIds") or {}).get("ArXiv"),
            "year": raw.get("year"), "authors": [a["name"] for a in raw.get("authors", [])],
            "abstract": raw.get("abstract"), "url": raw.get("url"), "pdf_url": (raw.get("openAccessPdf") or {}).get("url")}


def retry_delay(value):
    try:
        number = float(value)
        return max(0, number) if math.isfinite(number) else None
    except (ValueError, TypeError):
        try: return max(0, parsedate_to_datetime(value).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError): return None


def diagnostic(code, headers):
    result = {'http': code, 'category': 'ok' if code == 200 else 'rate_limited' if code == 429 else 'authentication_or_permission' if code in (401,403) else 'service_error' if code >= 500 else 'request_error'}
    # Only numeric quota fields survive: never log bodies, keys, cookies or URLs.
    for name in ('X-RateLimit-Limit','X-RateLimit-Remaining','X-RateLimit-Credits-Used','X-RateLimit-Reset'):
        value = headers.get(name, '')
        if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value): result[name.lower()] = value
    delay = retry_delay(headers.get('Retry-After',''))
    if delay is not None: result['retry_after_seconds'] = delay
    return result


class APIError(ResearchError):
    def __init__(self, provider, info):
        self.diagnostic = info
        labels = {'rate_limited':'服务端限流或额度耗尽','authentication_or_permission':'凭据或访问权限受阻','service_error':'服务端暂时故障','request_error':'请求被拒绝'}
        message = provider + ' HTTP ' + str(info['http']) + ' · ' + labels.get(info['category'],info['category'])
        if 'x-ratelimit-remaining' in info: message += '；剩余额度 ' + info['x-ratelimit-remaining']
        if 'retry_after_seconds' in info: message += '；建议等待 ' + str(round(info['retry_after_seconds'])) + ' 秒'
        super().__init__(message)


class AuthenticationRequired(ResearchError):
    pass


class Router:
    def __init__(self, store, offline=False, daily_limit=50, fresh=False, defer=False):
        self.store, self.offline, self.fresh = store, offline, fresh
        self.defer = defer
        if not 1 <= daily_limit <= 50:
            raise ResearchError("free_only 的每来源每日请求上限须在 1..50")
        self.daily_limit = daily_limit

    def reserve(self, provider):
        from . import request_gate
        try:
            request_gate.admit(provider, self.daily_limit)
        except request_gate.Deferred as exc:
            delay = max(0, exc.until-time.time())
            if self.defer or delay > 20: raise
            time.sleep(delay)
            request_gate.admit(provider, self.daily_limit)
        db = self.store.db
        day = datetime.now(timezone.utc).date().isoformat()
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT calls,last_request FROM usage WHERE day=? AND provider=?", (day, provider)).fetchone()
            calls, previous = (row[0], row[1]) if row else (0, 0)
            if calls >= self.daily_limit:
                raise request_gate.Deferred(request_gate.tomorrow(), provider + " 达到本地每日请求上限；排到次日")
            interval = 3.1 if provider == "arxiv" else 1.1
            scheduled = max(time.time(), previous + interval)
            db.execute("INSERT OR REPLACE INTO usage VALUES(?,?,?,?)", (day, provider, calls + 1, scheduled))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        time.sleep(max(0, scheduled - time.time()))

    def request(self, provider, endpoint, params):
        params = dict(params)
        key = hashlib.sha256(dumps([provider, endpoint, params]).encode()).hexdigest()
        row = self.store.db.execute("SELECT body,created FROM cache WHERE key=?", (key,)).fetchone()
        if row and (self.offline or (not self.fresh and time.time() - row[1] < 86400)):
            return row[0], {"cached": True, "cached_at": row[1]}
        if self.offline:
            raise ResearchError(provider + " 离线缓存未命中")
        headers = {"User-Agent": "VibeResearch/0.1 (local research orchestration)"}
        token, auth_source = credential(provider)
        if provider in ("wos", "scopus", "unpaywall") and not token:
            if provider == "unpaywall":
                raise AuthenticationRequired("unpaywall 需要先填写愿意发送给服务方的本人联系邮箱")
            raise AuthenticationRequired(provider + " 需要先完成官方授权与本机凭据配置")
        if provider == "openalex" and token:
            headers["Authorization"] = "Bearer " + token
        if provider == "s2" and token:
            headers["x-api-key"] = token
        if provider == "wos":
            headers["X-ApiKey"] = token
        if provider == "scopus":
            headers["X-ELS-APIKey"] = token
        if provider == "unpaywall":
            params["email"] = token
        url = endpoint + "?" + urllib.parse.urlencode(params)
        for attempt in range(1 if self.defer else 3):
            self.reserve(provider)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as response:
                    body = response.read(10_000_001)
                    response_info = diagnostic(response.status, response.headers)
                if len(body) > 10_000_000:
                    raise ResearchError("响应超过 10MB")
                body = body.decode("utf8")
                # Validate before caching; HTML errors must not poison the cache.
                ET.fromstring(body) if provider == "arxiv" else json.loads(body)
                with self.store.db:
                    self.store.db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?)", (key, provider, time.time(), body))
                return body, {"cached": False, "auth_source": auth_source, **response_info}
            except urllib.error.HTTPError as exc:
                info = {**diagnostic(exc.code, exc.headers), "auth_source": auth_source}
                delay = retry_delay(exc.headers.get("Retry-After", ""))
                if exc.code == 429:
                    from . import request_gate
                    request_gate.cool(provider, time.time() + (delay if delay is not None else 60))
                # Return quota errors to the durable queue immediately. Retrying a 429
                # used to replace its useful headers with a generic local-cooldown error.
                if not self.defer and exc.code in {500, 502, 503, 504} and attempt < 2:
                    delay = delay if delay is not None else 2 ** (attempt + 1)
                    if delay <= 20:
                        time.sleep(delay)
                        continue
                raise APIError(provider, info) from None
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, ET.ParseError):
                if not self.defer and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ResearchError(provider + " 网络、代理、TLS 或响应解析失败；未收到可用 API 结果，不能判断为限流") from None
        raise ResearchError("请求失败")

    def search(self, query, provider="auto", limit=10):
        if not query.strip() or not 1 <= limit <= 100:
            raise ResearchError("需要查询文本，limit 应在 1..100")
        attempts = []
        for p in PROVIDERS if provider == "auto" else [provider]:
            try:
                if p == "openalex":
                    body, info = self.request(p, "https://api.openalex.org/works", {"search": query, "per_page": limit})
                    papers = [normalize(p, x) for x in json.loads(body)["results"]]
                elif p == "s2":
                    body, info = self.request(p, "https://api.semanticscholar.org/graph/v1/paper/search", {"query": query, "limit": limit, "fields": FIELDS})
                    papers = [normalize(p, x) for x in json.loads(body)["data"]]
                elif p == "arxiv":
                    body, info = self.request(p, "https://export.arxiv.org/api/query", {"search_query": "all:" + query, "start": 0, "max_results": limit})
                    ns = {"a": "http://www.w3.org/2005/Atom"}
                    papers = []
                    for entry in ET.fromstring(body).findall("a:entry", ns):
                        ident = entry.findtext("a:id", namespaces=ns)
                        if "/api/errors" in (ident or ""):
                            raise ResearchError("arXiv 查询语法错误")
                        papers.append({"provider": p, "external_id": ident, "arxiv": ident.rsplit("/abs/", 1)[-1],
                                       "title": " ".join(entry.findtext("a:title", default="", namespaces=ns).split()),
                                       "abstract": entry.findtext("a:summary", namespaces=ns),
                                       "year": int(entry.findtext("a:published", namespaces=ns)[:4]),
                                       "authors": [a.findtext("a:name", namespaces=ns) for a in entry.findall("a:author", ns)],
                                       "url": ident, "pdf_url": next((l.attrib["href"] for l in entry.findall("a:link", ns) if l.attrib.get("title") == "pdf"), None)})
                elif p in ('crossref','core','huggingface','wos','scopus','unpaywall'):
                    page=search_page(self,query,p,size=limit)
                    papers=page['papers'];info=page['diagnostic']
                else:
                    raise ResearchError("未知来源")
                attempts.append({"provider": p, "count": len(papers), **info})
                if papers or provider != "auto":
                    return {"query": query, "policy": "free_only", "attempts": attempts, "papers": papers, "retrieved_at": now()}
            except (ResearchError, KeyError, TypeError, ValueError) as exc:
                attempts.append({"provider": p, "error": str(exc), "diagnostic": getattr(exc,"diagnostic",{})})
        error = ResearchError("检索未获得结果：" + "；".join(a.get("error", a["provider"]+" 无命中") for a in attempts))
        error.attempts = attempts
        raise error

    def expand(self, paper, direction="references", limit=20):
        data = paper["data"]
        record = data.get("bibliography", {})
        pid = record.get("doi")
        pid = "DOI:" + clean_doi(pid) if pid else ("ARXIV:" + record["arxiv"] if record.get("arxiv") else record.get("external_id") if record.get("provider") == "s2" else None)
        if not pid:
            raise ResearchError("扩引需要 DOI、arXiv ID 或 Semantic Scholar ID")
        body, info = self.request("s2", "https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote(pid, safe="") + "/" + direction, {"fields": FIELDS, "limit": limit})
        field = "citedPaper" if direction == "references" else "citingPaper"
        papers = [normalize("s2", r[field]) for r in json.loads(body)["data"] if r.get(field) and r[field].get("paperId")]
        return {"papers": papers, "direction": direction, "source": paper["id"], **info}


def clean_doi(value):
    return re.sub(r"^(https?://(dx\.)?doi.org/|doi:)", "", value.strip(), flags=re.I).lower()


def identifiers(paper):
    result = set()
    if paper.get("doi"):
        result.add("doi:" + clean_doi(paper["doi"]))
    if paper.get("arxiv"):
        result.add("arxiv:" + re.sub(r"v\d+$", "", paper["arxiv"]))
    if paper.get("external_id"):
        result.add(paper["provider"] + ":" + paper["external_id"])
    return result


def import_paper(store, paper, branch=None):
    if not isinstance(paper, dict) or not paper.get("title"):
        raise ResearchError("论文记录缺少 title")
    incoming = identifiers(paper)
    for node in store.rows("nodes"):
        if node["kind"] == "P" and incoming & identifiers(node["data"].get("bibliography", {})):
            if branch:
                store.add_member(branch, node["id"])
            return node["id"]
    return store.add_node("P", paper["title"], {"bibliography": paper, "reading_status": "metadata_only"}, branch)


def search_page(router, query, provider, cursor=None, size=25):
    """One page only. Return an explicit cursor and never infer coverage from fallback."""
    if provider not in ALL_SOURCES or not query.strip() or not 1 <= size <= 100:
        raise ResearchError('无效的分页检索参数')
    boundary = None
    if provider == 'openalex':
        body, info = router.request(provider, 'https://api.openalex.org/works',
                                    {'search':query,'per_page':size,'cursor':cursor or '*'})
        data=json.loads(body); raw=data['results']; total=int(data['meta']['count'])
        papers=[normalize(provider,x) for x in raw]
        nxt=data['meta'].get('next_cursor') if raw else None
        if (not raw and cursor is None and total>0) or (raw and len(raw)==size and not nxt and total>len(raw)):
            boundary='来源未提供下一页游标，需核查检索范围'
    elif provider == 's2':
        offset=int(cursor or 0)
        body, info=router.request(provider,'https://api.semanticscholar.org/graph/v1/paper/search',
                                  {'query':query,'limit':size,'offset':offset,'fields':FIELDS})
        data=json.loads(body); papers=[normalize(provider,x) for x in data['data']];total=int(data['total'])
        nxt=str(data['next']) if data.get('next') is not None else None
        if offset+len(papers)<total and (nxt is None or int(nxt)>=1000):
            boundary='Semantic Scholar 相关性检索窗口受限；需拆分查询或改用批量检索，不能视为覆盖完成'
            nxt=None
    elif provider=='arxiv':
        offset=int(cursor or 0)
        body,info=router.request(provider,'https://export.arxiv.org/api/query',
             {'search_query':'all:'+query,'start':offset,'max_results':size,'sortBy':'submittedDate','sortOrder':'ascending'})
        tree=ET.fromstring(body);ns={'a':'http://www.w3.org/2005/Atom','o':'http://a9.com/-/spec/opensearch/1.1/'}
        total=int(tree.findtext('o:totalResults',namespaces=ns));papers=[]
        for e in tree.findall('a:entry',ns):
            ident=e.findtext('a:id',namespaces=ns)
            if not ident or '/api/errors' in ident: raise ResearchError('arXiv 返回查询错误')
            papers.append({'provider':provider,'external_id':ident,'arxiv':ident.rsplit('/abs/',1)[-1],
                'title':' '.join(e.findtext('a:title',default='',namespaces=ns).split()),
                'abstract':e.findtext('a:summary',namespaces=ns),'year':int(e.findtext('a:published',namespaces=ns)[:4]),
                'authors':[a.findtext('a:name',namespaces=ns) for a in e.findall('a:author',ns)],'url':ident,
                'pdf_url':next((l.attrib['href'] for l in e.findall('a:link',ns) if l.attrib.get('title')=='pdf'),None)})
        nxt=str(offset+len(papers)) if offset+len(papers)<total else None
        if nxt and (not papers or int(nxt)>=30000):
            boundary='arXiv 返回空页或达到检索窗口；需要按时间拆分查询';nxt=None
    elif provider=='crossref':
        body,info=router.request(provider,'https://api.crossref.org/works',{'query':query,'rows':size,'cursor':cursor or '*'})
        data=json.loads(body)['message'];raw=data['items'];total=int(data['total-results']);papers=[]
        for x in raw:
            parts=(x.get('issued') or {}).get('date-parts') or [[None]]
            papers.append({'provider':provider,'external_id':x['DOI'],'doi':x['DOI'],'title':(x.get('title') or ['Untitled'])[0],
                'year':parts[0][0],'authors':[' '.join(filter(None,[a.get('given'),a.get('family')])) for a in x.get('author',[])],
                'abstract':x.get('abstract'),'url':x.get('URL'),'pdf_url':None})
        nxt=data.get('next-cursor') if len(raw)==size else None
        if len(raw)==size and not nxt:boundary='Crossref 未提供下一页游标，需核查范围'
    elif provider=='core':
        offset=int(cursor or 0)
        body,info=router.request(provider,'https://api.core.ac.uk/v3/search/works',{'q':query,'limit':size,'offset':offset})
        data=json.loads(body);raw=data['results'];total=int(data['totalHits']);papers=[]
        for x in raw:
            papers.append({'provider':provider,'external_id':str(x['id']),'doi':x.get('doi'),'arxiv':x.get('arxivId'),
                'title':x.get('title') or 'Untitled','year':x.get('yearPublished'),
                'authors':[a.get('name','') if isinstance(a,dict) else str(a) for a in x.get('authors',[])],
                'abstract':x.get('abstract'),'url':'https://core.ac.uk/works/'+str(x['id']),'pdf_url':x.get('downloadUrl') or None})
        nxt=str(offset+len(raw)) if offset+len(raw)<total else None
        if nxt and (not raw or int(nxt)>=10000):boundary='CORE 空页或检索窗口限制，需拆分查询';nxt=None
    elif provider=='huggingface':
        body,info=router.request(provider,'https://huggingface.co/api/papers/search',{'q':query,'limit':size})
        data=json.loads(body);papers=[];total=None;nxt=None
        if not isinstance(data,list):raise ResearchError('Hugging Face 响应格式异常')
        for item in data:
            x=item['paper'];ident=x['id']
            papers.append({'provider':provider,'external_id':ident,'arxiv':ident,'title':x['title'],
                'abstract':x.get('summary'),'authors':[a.get('name','') for a in x.get('authors',[])],
                'year':int(x['publishedAt'][:4]) if x.get('publishedAt') else None,
                'url':'https://huggingface.co/papers/'+ident,'pdf_url':None})
        boundary='Hugging Face 为发现型来源，当前接口无已验证的完整分页；不能声明全覆盖'
    elif provider=='wos':
        page=int(cursor or 1)
        body,info=router.request(provider,'https://api.clarivate.com/apis/wos-starter/v1/documents',
            {'q':query,'db':'WOS','limit':size,'page':page})
        data=json.loads(body);raw=data.get('hits') or [];meta=data.get('metadata') or {};papers=[]
        for x in raw:
            names=x.get('names') or {};source=x.get('source') or {};ids=x.get('identifiers') or {};links=x.get('links') or {}
            authors=names.get('authors') or []
            papers.append({'provider':provider,'external_id':x.get('uid') or ids.get('doi') or x.get('title'),
                'doi':ids.get('doi'),'title':x.get('title') or 'Untitled','year':source.get('publishYear'),
                'authors':[(a.get('displayName') or a.get('wosStandard') or a.get('name') or '') if isinstance(a,dict) else str(a) for a in authors],
                'abstract':x.get('abstract'),'url':links.get('record') or links.get('source'),'pdf_url':None})
        total=int(meta.get('total') or meta.get('totalRecords') or len(raw))
        nxt=str(page+1) if raw and page*size<total else None
    elif provider=='scopus':
        offset=int(cursor or 0)
        body,info=router.request(provider,'https://api.elsevier.com/content/search/scopus',
            {'query':query,'count':size,'start':offset,'view':'STANDARD'})
        data=json.loads(body).get('search-results') or {};raw=data.get('entry') or [];papers=[]
        for x in raw:
            ident=str(x.get('dc:identifier') or x.get('eid') or x.get('prism:doi') or x.get('dc:title'))
            date=x.get('prism:coverDate') or '';authors=x.get('author') or []
            papers.append({'provider':provider,'external_id':ident,'doi':x.get('prism:doi'),
                'title':x.get('dc:title') or 'Untitled','year':int(date[:4]) if re.fullmatch(r'\d{4}.*',date) else None,
                'authors':[(a.get('authname') or a.get('given-name') or '') if isinstance(a,dict) else str(a) for a in authors],
                'abstract':x.get('dc:description'),'url':x.get('prism:url') or next((l.get('@href') for l in x.get('link',[]) if l.get('@ref')=='scopus'),None),'pdf_url':None})
        total=int(data.get('opensearch:totalResults') or len(raw))
        nxt=str(offset+len(raw)) if raw and offset+len(raw)<total else None
    elif provider=='unpaywall':
        doi=clean_doi(query)
        if not doi.startswith('10.') or '/' not in doi:raise ResearchError('Unpaywall 任务需要 DOI，不能使用关键词')
        body,info=router.request(provider,'https://api.unpaywall.org/v2/'+urllib.parse.quote(doi,safe=''),{})
        x=json.loads(body);best=x.get('best_oa_location') or {};authors=x.get('z_authors') or []
        papers=[{'provider':provider,'external_id':doi,'doi':doi,'title':x.get('title') or 'Untitled','year':x.get('year'),
            'authors':[' '.join(filter(None,[a.get('given'),a.get('family')])) for a in authors if isinstance(a,dict)],
            'abstract':None,'url':x.get('doi_url') or ('https://doi.org/'+doi),'pdf_url':best.get('url_for_pdf') or best.get('url')}]
        total=1;nxt=None
    else:
        raise ResearchError('未知来源')
    if not isinstance(papers,list) or any(not p.get('external_id') or not p.get('title') for p in papers):
        raise ResearchError('来源响应缺少必要书目字段')
    if nxt is not None and str(nxt)==str(cursor):
        boundary='来源重复返回相同游标，已保留结果并停止翻页';nxt=None
    return {'papers':papers,'next_cursor':nxt,'total':total,'boundary':boundary,'diagnostic':info}
