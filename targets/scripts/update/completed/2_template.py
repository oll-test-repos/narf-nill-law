import sys
import json
from lxml import html
from lxml.builder import E
import os.path
import os
from pathlib import Path
from copy import deepcopy
from urllib.parse import urlsplit
from taf.auth_repo import AuthenticationRepository
from taf.git import GitRepository
from taf.log import taf_logger


H_OFFSET = 2
URL_PREFIX = '/nill/triballaw'
LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()
# LIB_ROOT_PATH = Path("/home/dnikolic/narf")
if not LIB_ROOT_PATH.exists():
    raise(Exception(f'archive at {LIB_ROOT_PATH} does not exist.'))

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.parent.absolute()
# BASE_DIR = Path("/home/dnikolic/narf/narf-nill")
NILL_LAW_DIR = Path(BASE_DIR / 'law')
# BASE_DIR = Path("/home/dnikolic/narf/openlawlibrary/nill")
DST_ROOT_PATH = Path(BASE_DIR / 'law-html' / 'triballaw')

TEMPLATE_BASE_DIR = DST_ROOT_PATH / 'templates'

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

def get_official_site(url):
    official_site = [
        E.a("website", href=url, target="_blank")
    ]
    return official_site

def get_live_site(url):
    live_site = [
        E.a("law library", href=url, target="_blank")
    ]
    return live_site

def get_tribes_nill_page(url, tribes_full_name):
    tribes_nill_page = [
        E.a(tribes_full_name, href=url)
    ]
    return tribes_nill_page

def template(template, base_src_path, rel_src_path, domain, tribe_config, namespace=None):
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
        "meta": get_document_meta(src),
        "content": [src_content],
        "footer": get_footer(src),
        "official-site": get_official_site(tribe_config["official-site"]),
        "live-site": get_live_site(domain),
        "tribes-nill-page": get_tribes_nill_page(tribe_config["tribes-nill-page"], tribe_config["tribe-full-name"]),
        "tribe-full-name": tribe_config["tribe-full-name"],
        "tribe": tribe_config["tribe"],
        "breadcrumbs": get_breadcrumbs(src),
    }

    replace_elements = template.xpath('//replace')
    for replace_el in replace_elements:
        name = replace_el.get('name')
        replacements = replacements_by_name.get(name, [])
        if isinstance(replacements, str):
            replace_el.tail = replacements + replace_el.tail if replace_el.tail else replacements
            replace_el.drop_tag()
            continue
        for r in reversed(replacements):
            replace_el.addnext(r)
            if replace_el.tail:
                if not replace_el.tail.isspace():
                    r.tail = replace_el.tail
                    replace_el.tail = None
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

def is_jurisdiction_already_templated(jurisdiction):
    """
    Read .metadata.json file and check if the last validated commit is the same as the current commit in the authentication repository.
    """
    try:
        current_commit = get_current_targets_commit(jurisdiction, targets_type="law-html")
    except (TypeError, KeyError):
        # no target file for this jurisdiction
        # no need to template anything, since jursdiction has no html.
        return True
    except Exception as e:
        taf_logger.error(f"Could not get current commit for {jurisdiction}: {e}")
        raise e
    metadata_path = BASE_DIR / "law-html" / ".metadata.json"
    if not metadata_path.exists():
        return False
    metadata = json.loads(metadata_path.read_text())
    last_validated_commit = metadata.get(f"{jurisdiction}/law-html", {}).get("last_validated_commit")
    if last_validated_commit is None:
        return False
    return last_validated_commit == current_commit

def get_rel_dst_path(rel_src_path, namespace=None):
    if str(rel_src_path.parent) == '.' and namespace:
        rel_src_path = Path(namespace) / rel_src_path
    if rel_src_path.suffix != '.html' or rel_src_path.name in ("index.html", "index.full.html"):
        rel_dst_path =  rel_src_path
    else:
        new_folder = rel_src_path.name.rsplit('.', 1)[0]
        rel_dst_path = rel_src_path.parent / new_folder / 'index.html'
    return rel_dst_path

def get_template():
    template_path = TEMPLATE_BASE_DIR / 'template.html'
    template_text = template_path.read_text()
    template = html.fromstring(template_text)
    return template

def get_domain(jurisdiction):
    """Parse the law-html repository and look for the 'html' tag from metadata.json 'canonical_url'"""
    html_repo_path = (BASE_DIR / ".." / jurisdiction / "law-html").resolve()
    html_repo = GitRepository(path=html_repo_path)
    metadata = html_repo.safely_get_json("HEAD", "metadata.json")
    if metadata is None:
        return None
    try:
        html_tag = metadata["meta"]["canonical-urls"]["html"]
        return html_tag.get("current") if isinstance(html_tag, dict) else html_tag
    except (TypeError, KeyError, AttributeError):
        return None

def get_current_targets_commit(jurisdiction, targets_type="law-html"):
    """
    Get the current signed commit for the law-html repository.
    """
    law_repo_path = (BASE_DIR / ".." / jurisdiction / "law").resolve()
    law_repo = AuthenticationRepository(path=law_repo_path)
    targets = law_repo.get_target(f"{jurisdiction}/{targets_type}")
    return targets["commit"]

def get_jurisdiction_map():
    """
    Return a mapping of jurisdiction to entity_id in the form of:
    jurisdiction_map = {
        jurisdiction_org: entity_id
    }
    e.g.
    jurisdiction_map = {
        'sanipueblo': 'us/nsn/san-ildefonso/council',
        'mohicanlaw': 'us/nsn/mohican/council',
    }
    """
    nill_law_repo = AuthenticationRepository(path=NILL_LAW_DIR)
    dependencies = nill_law_repo.safely_get_json("HEAD", "targets/dependencies.json")
    if dependencies is None:
        return None
    jurisdiction_map = {}
    jurisdiction_orgs = dependencies.get("dependencies", {}).keys()
    for jurisdiction in jurisdiction_orgs:
        jurisdiction = jurisdiction.split("/")[0]
        law_repo_path = (BASE_DIR / ".." / jurisdiction / "law").resolve()
        law_repo = GitRepository(path=law_repo_path)
        requirements_txt = law_repo.get_file("HEAD", "requirements.txt")
        entity_id = get_entity_id_from_requirements(requirements_txt)
        jurisdiction_map[jurisdiction] = entity_id
    return jurisdiction_map

def get_jurisdiction_paths():
    return [LIB_ROOT_PATH / k for k in get_jurisdiction_map().keys()]

def get_entity_id_from_requirements(requirements_txt):
    entity_id = None
    for line in requirements_txt.split("\n"):
        if "#" in line:
            entity_id = line.split("#")[-1].strip()
            break
    # omit oll.partners part and replace . with / and _ with -
    entity_id = entity_id.replace("oll.partners.", "").replace(".", "/").replace("_", "-")
    return entity_id

def get_template_config():
    return json.loads((TEMPLATE_BASE_DIR / 'template_config.json').read_text())

def get_template_config(domain):
    return json.loads((TEMPLATE_BASE_DIR / f'template_config.json').read_text()).get(domain, None)

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    # printed data will be sent from the script back to the updater
    print(json.dumps(state))

def set_metadata_json(new_metadata):
    metadata_path = BASE_DIR / "law-html" / ".metadata.json"
    if not metadata_path.exists():
        metadata = {}
    else:
        metadata = json.loads(metadata_path.read_text())
    metadata.update(new_metadata)
    metadata_path.write_text(json.dumps(metadata, indent=2))

jurisdiction_map = get_jurisdiction_map()

if jurisdiction_map is None:
    raise Exception("Could not get jurisdiction map")

for jurisdiction_path in get_jurisdiction_paths():
    repos = (
        jurisdiction_path / 'law-html',
        jurisdiction_path / 'law-docs',
        jurisdiction_path / 'law-static-assets',
        jurisdiction_path / '..' / 'openlawlibrary' / 'law-static-assets',
    )
    jurisdiction = jurisdiction_path.stem
    if is_jurisdiction_already_templated(jurisdiction):
        taf_logger.info(f"Jurisdiction {jurisdiction} is already templated.")
        continue
    namespace = jurisdiction_map.get(jurisdiction)
    _template = get_template()
    domain = get_domain(jurisdiction)
    template_tribe_config = get_template_config(domain)

    for base_src_path, rel_src_path in iter_files(repos):
        dst_path = DST_ROOT_PATH / get_rel_dst_path(rel_src_path, namespace)
        dom = template(_template, base_src_path, rel_src_path, domain, template_tribe_config, namespace)
        if dom is not None:
            content = html.tostring(dom, encoding="utf-8")
        else:
            src_path = base_src_path / rel_src_path
            content = src_path.read_bytes()
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(content)
    new_metadata = {
        f"{jurisdiction}/law-html": {
            "last_validated_commit": get_current_targets_commit(jurisdiction, targets_type="law-html")
        }
    }
    set_metadata_json(new_metadata)

