"""Small cloud-generated review sheets linked to unmodified full page proofs."""
import json
from pathlib import Path
import os
import shutil
from PIL import Image, ImageDraw

if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'): raise RuntimeError('CLOUD_ONLY')

folder = Path('build/review'); folder.mkdir(parents=True, exist_ok=True)
reports = []
for index, source in enumerate(sorted(Path('build').rglob('render-report.json'))):
    if folder in source.parents: continue
    report = json.loads(source.read_text())
    identity = source.parent.relative_to(Path('build')).as_posix()
    entry = {'proof': identity, 'report': report, 'sheets': []}
    target = folder / str(index); target.mkdir(exist_ok=True)
    shutil.copyfile(source, target / 'render-report.json')
    for start in range(0, len(report['pages']), 4):
        sheet = Image.new('RGB', (1320, 1930), 'white'); draw = ImageDraw.Draw(sheet)
        for offset, page in enumerate(report['pages'][start:start + 4]):
            image = Image.open(source.parent / page['file']).convert('RGB')
            image.thumbnail((640, 915))
            x, y = (offset % 2) * 660 + 10, (offset // 2) * 965 + 35
            sheet.paste(image, (x, y)); draw.text((x, y - 25), identity + ' / page ' + str(start + offset + 1), fill='black')
        name = 'sheet-' + str(start // 4 + 1) + '.png'; sheet.save(target / name)
        entry['sheets'].append(str(index) + '/' + name)
    reports.append(entry)
(folder / 'index.json').write_text(json.dumps({'run_id': os.environ['GITHUB_RUN_ID'], 'proofs': reports}, ensure_ascii=False, indent=2))
