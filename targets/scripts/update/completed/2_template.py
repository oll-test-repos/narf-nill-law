import json
from lxml import html
from lxml.builder import E
import os.path
import os
from pathlib import Path
from copy import deepcopy
from urllib.parse import urlsplit
import requests
import sys

# JURISDICTION_MAP = {
#     partner org name: entity_id
# }
# TODO: to make flexibile, 
# partner org names can be taken from dependencies.json, 
# entity_ids from requirements.txt of the law repository
JURISDICTION_MAP = {
    'sanipueblo': 'us/nsn/san-ildefonso/council',
    'mohicanlaw': 'us/nsn/mohican/council',
}

H_OFFSET = 2
URL_PREFIX = '/nill/triballaw'
#test
LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()
# LIB_ROOT_PATH = Path("/home/dnikolic/narf")
if not LIB_ROOT_PATH.exists():
    raise(Exception(f'archive at {LIB_ROOT_PATH} does not exist.'))

PARTNER_PATHS = [LIB_ROOT_PATH / k for k in JURISDICTION_MAP.keys()]
# TODO: base dir should point to law-html / triballaw
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.parent.absolute()
# BASE_DIR = Path("/home/dnikolic/narf/narf-nill")
# BASE_DIR = Path("/home/dnikolic/narf/openlawlibrary/nill")
DST_ROOT_PATH = Path(BASE_DIR / 'law-html' / 'triballaw')

TEMPLATE_BASE_URL = 'https://www.narf.org/nill/triballaw/templates/'
# TEMPLATE_BASE_URL = 'http://localhost:8000/nill/triballaw/templates/'

def _update_urls_in_place(src, namespace, attr):
    els = src.xpath(f'//*[@{attr}]')
    for el in els:
        url = el.get(attr)
        if url.split('#')[0] == '/' and namespace:
            url = '/' + namespace + url[1:]
        
        if url.startswith('/'):
            el.set(attr, URL_PREFIX + url)
        elif url.startswith('./'):
            el.set(attr, '.' + url)
def update_urls_in_place(src, namespace):
    _update_urls_in_place(src, namespace, 'href')
    _update_urls_in_place(src, namespace, 'src')
    _update_urls_in_place(src, namespace, 'data')

def update_headings_in_place(src):
    probable_h_els = src.xpath('//*[starts-with(name(), "h")][string-length(name())=2]')
    for el in probable_h_els:
        num = el.tag[1]
        try:
            num = int(num)
        except ValueError:
            continue
        num += H_OFFSET
        new_tag = f'h{num}'
        el.tag = new_tag

def get_head(src):
    out = []
    for meta in src.iter('meta'):
        if meta.get('itemprop') in ("toc-json", "full-html", "parent-doc-url"):
            meta.set('content', URL_PREFIX + meta.get('content'))
        if meta.get('itemprop') in ("toc-json", "doc-type", "ref-doc", "full-html", "parent-doc-url", "ref-path"):
            out.append(meta)
    out += src.xpath('//head/link[@type="text/css"][not(contains(@href, "_reader"))]')
    out += src.xpath('//head/script')
    return out

def get_document_meta(src):
    document_meta = src.xpath('//section[@id="area__document_meta"]')
    if document_meta:
        return [document_meta[0]]
    else:
        return []


def get_breadcrumbs(src):
    src_bc_els = src.xpath('//nav[@aria-label="Breadcrumb navigation"]/ul/li/*')
    for el in src_bc_els:
        el.tail = ' | '
    src_bc_els[0].set('title', 'Collection')
    src_bc_els[0].text = 'Collection'
    src_bc_els[-1].tail = ''
    return src_bc_els

def get_footer(src):
    og_url = src.xpath('//meta[@property="og:url"]/@content')[0]
    if not og_url:
        import pdb; pdb.set_trace()

    footer = [
        E.p('Original url: ', E.a(og_url, href=og_url)),
        E.p('Powered by the non-profit ', E.a('Open Law Library.', href='https://openlawlib.org'))
    ]
    if urlsplit(og_url).path == '/':
        footer.extend([
            E.img(src="https://www.imls.gov/sites/default/files/imls_logo_2c.gif", alt="Institute of Museum and Library Services logo", style="width: 40%; margin: .25in 0; max-width: 325px; min-width: 200px;"),
            E.p('This project was made possible in part by the Institute of Museum and Library Services (', E.a('LG-246285-OLS-20', href="https://www.imls.gov/grants/awarded/lg-246285-ols-20", target="_blank"), ').', style="width: 40%; max-width: 325px; min-width: 200px;"),
        ])
    return footer

def template(template, base_src_path, rel_src_path, namespace=None):
    """
    given a source path:
    * parse src html
    * move urls pointing to root to point to namespace if namespace is provided
    * properly prefix all absolute urls
    * properly increment h* tags
    * template dst html from source html
    * return string suitable for writing to file
    """
    if rel_src_path.suffix != '.html':
        # do not template non-html files
        return None
    src_path = base_src_path / rel_src_path
    src = html.parse(str(src_path)).getroot()
    try:
        src_content = src.xpath('.//main')[0]
    except IndexError:
        # skip .html files that don't have a main element
        return None
    update_urls_in_place(src, namespace)
    update_headings_in_place(src)

    template = deepcopy(template)

    auth_el = src.xpath('.//div[@class="tuf-authenticate"]')[0]
    auth_el.set('data-url-prefix', URL_PREFIX)
    auth_el.set('data-h-offset', str(H_OFFSET))

    replacements_by_name = {
        "head": get_head(src),
        "breadcrumbs": get_breadcrumbs(src),
        "meta": get_document_meta(src),
        "content": [src_content],
        "footer": get_footer(src),
    }

    replace_elements = template.xpath('//replace')
    for replace_el in replace_elements:
        name = replace_el.get('name')
        replacements = replacements_by_name.get(name, [])
        for r in reversed(replacements):
            replace_el.addnext(r)
        replace_el.getparent().remove(replace_el)

    return template

def iter_files(base_paths, skip_dotfiles=True):
    print(base_paths)
    for base_path in base_paths:
        print(base_path)
        if not os.path.exists(base_path):
            continue
        for root, dirs, files in os.walk(str(base_path)):
            for d in reversed(dirs):
                if skip_dotfiles and d.startswith('.'):
                    dirs.remove(d)
            rel_root_path = Path(root).relative_to(base_path)
            for f in files:
                if skip_dotfiles and f.startswith('.'):
                    continue
                yield base_path, rel_root_path / f

def get_rel_dst_path(rel_src_path, namespace=None):
    if str(rel_src_path.parent) == '.' and namespace:
        rel_src_path = Path(namespace) / rel_src_path
    if rel_src_path.suffix != '.html' or rel_src_path.name in ("index.html", "index.full.html"):
        rel_dst_path =  rel_src_path
    else:
        new_folder = rel_src_path.name.rsplit('.', 1)[0]
        rel_dst_path = rel_src_path.parent / new_folder / 'index.html'
    return rel_dst_path

def get_template(namespace):
    template_url = TEMPLATE_BASE_URL + namespace + '/template.html'
    resp = requests.get(template_url)
    # requests for some reason thinks the document is encoded ISO-8859-1 (win default)
    # but it is utf-8, so must use content (bytes), not text (str)
    template_text = resp.content
    template_text = template_text.replace(b'="../../../../../../', b'="/nill/')
    template_text = template_text.replace(b'="../../../../../', b'="/nill/triballaw/')

    template = html.fromstring(template_text)
    return template

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    # printed data will be sent from the script back to the updater
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)
# with open("/home/dnikolic/.RESULT/TEMPLATE.txt", "w+") as f:
#     f.write(f"DATA {data}\n")
state = data["state"]
config = data["config"]

for partner_path in PARTNER_PATHS:
    repos = (
        partner_path / 'law-html',
        partner_path / 'law-docs',
        partner_path / 'law-static-assets',
        partner_path / '..' / 'openlawlibrary' / 'law-static-assets',
    )
    jurisdiction = partner_path.stem
    namespace = JURISDICTION_MAP.get(jurisdiction)
    _template = get_template(namespace)

    for base_src_path, rel_src_path in iter_files(repos):
        dst_path = DST_ROOT_PATH / get_rel_dst_path(rel_src_path, namespace)
        dom = template(_template, base_src_path, rel_src_path, namespace)
        if dom is not None:
            content = html.tostring(dom, encoding="utf-8")
        else:
            src_path = base_src_path / rel_src_path
            content = src_path.read_bytes()
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(content)

send_state(state)