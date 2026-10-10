"""Check the reviewed repository inventory, install scope and real README pages."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from word_module_studio.distribution import publication_manifest
from word_module_studio.runtime import require_actions, WordError, digest, write_json

FORBIDDEN_PARTS = {
    '.git', '.downloads', '.tools', 'build', 'dist', 'outputs', 'jobs', 'tasks',
    'private-inputs', 'excluded', '__pycache__', 'node_modules', 'consumers',
    'consumer-policies', 'public-paper', 'model',
}
ROOT_FILES = {
    '.gitignore', 'LICENSE', 'README.md', 'README.zh-CN.md', 'THIRD_PARTY_NOTICES.md',
    'pins.json', 'pyproject.toml', 'publication-manifest.json',
    'requirements.lock', 'requirements-resolved.lock',
}
ROOT_PREFIXES = (
    '.github/workflows/', 'ci/', 'docs/', 'examples/', 'schemas/', 'scripts/',
    'sdk/', 'skills/word-module-studio/', 'src/word_module_studio/', 'tests/',
    'third_party/', 'fixtures/upstream/word/',
)


def inspect():
    require_actions()
    inventory = publication_manifest()
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')) - {''}
    approved = set(inventory['repository_files'])
    if tracked != approved:
        raise WordError('PUBLICATION_INVENTORY_MISMATCH', json.dumps({
            'unreviewed_tracked_files': sorted(tracked - approved),
            'missing_tracked_files': sorted(approved - tracked),
        }))
    for name in sorted(tracked):
        path = Path(name)
        if any(part in FORBIDDEN_PARTS for part in path.parts) or path.name in ('test_consumer.py', 'test_public_paper.py'):
            raise WordError('PUBLICATION_OUT_OF_SCOPE', name)
        if name not in ROOT_FILES and not name.startswith(ROOT_PREFIXES):
            raise WordError('PUBLICATION_OUT_OF_SCOPE', name)
    if any(name.startswith(('tests/', 'fixtures/', 'scripts/')) for name in inventory['core_files']):
        raise WordError('INSTALLATION_CONTAINS_DEVELOPMENT_INPUTS')

    # README paths work both on GitHub and in the packaged core directory.
    for readme in ('README.md', 'README.zh-CN.md'):
        text = (ROOT / readme).read_text(encoding='utf-8-sig')
        links = re.findall(r'\]\(([^)]+)\)', text) + re.findall(r'src="([^"]+)"', text)
        for link in links:
            if link.startswith(('https://', 'http://', '#')): continue
            relative = unquote(link.split('#', 1)[0])
            if relative not in approved or not (ROOT / relative).is_file():
                raise WordError('README_LOCAL_LINK_INVALID', readme + ': ' + relative)
        other = 'README.zh-CN.md' if readme == 'README.md' else 'README.md'
        if '](' + other + ')' not in text: raise WordError('README_LANGUAGE_LINK_MISSING', readme)

    gallery = json.loads((ROOT / 'docs/gallery/provenance.json').read_text())
    accepted = json.loads((ROOT / 'docs/core-acceptance.json').read_text())
    proofs = {entry['receipt']: entry for entry in accepted['proofs']}
    displayed = set()
    for entry in gallery['images']:
        name = 'docs/gallery/' + entry['file']
        if name not in approved or digest(ROOT / name) != entry['sha256']:
            raise WordError('GALLERY_IMAGE_CHANGED', name)
        receipt = json.loads((ROOT / entry['receipt']).read_text())
        page = receipt['pages'][entry['page_number'] - 1]
        if page['file'] != entry['source_page'] or page['sha256'] != entry['sha256']:
            raise WordError('GALLERY_PAGE_NOT_ACCEPTED', name)
        if proofs[entry['receipt']]['path'] != entry['source_proof'] or receipt['run_id'] != gallery['run_id']:
            raise WordError('GALLERY_PROVENANCE_MISMATCH', name)
        for readme in ('README.md', 'README.zh-CN.md'):
            if 'src="' + name + '"' not in (ROOT / readme).read_text():
                raise WordError('GALLERY_IMAGE_NOT_DISPLAYED', readme + ': ' + name)
        displayed.add(name)
    if displayed != {name for name in approved if name.startswith('docs/gallery/') and name.endswith('.png')}:
        raise WordError('GALLERY_INVENTORY_MISMATCH')

    # The validator confirms the portable skill's frontmatter and metadata agreement.
    import yaml
    skill = (ROOT / 'skills/word-module-studio/SKILL.md').read_text()
    metadata = yaml.safe_load(skill.split('---', 2)[1])
    if metadata.get('name') != 'word-module-studio' or not metadata.get('description'):
        raise WordError('SKILL_METADATA_INVALID')
    if len(metadata['name']) > 64 or not re.fullmatch(r'[a-z0-9-]+', metadata['name']):
        raise WordError('SKILL_NAME_INVALID')
    report = {
        'schema_version': 1, 'automatic_pass': True,
        'repository_file_count': len(approved), 'core_file_count': len(inventory['core_files']),
        'skill_file_count': len(inventory['skill_files']), 'gallery_image_count': len(displayed),
        'scope': 'standalone generic DOCX skill', 'unreviewed_tracked_files': [],
        'application_specific_inputs_present': False,
        'local_readme_links_valid': True, 'gallery_images_match_accepted_pages': True,
    }
    write_json(ROOT / 'build/publication-audit.json', report)
    return report


if __name__ == '__main__':
    print(json.dumps(inspect(), indent=2))
