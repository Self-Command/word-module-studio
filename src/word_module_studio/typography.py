"""Adapters to pinned OfficeCLI format properties and SDK native layout objects."""
from pathlib import Path
import tempfile
from .runtime import require_actions, WordError, run, digest
from .backend import OfficeBackend

DOCUMENT_PROPERTIES = {'docGrid.type', 'docGrid.linePitch', 'docGrid.charSpace', 'charSpacingControl', 'autoHyphenation',
    'autoSpaceDE', 'autoSpaceDN', 'kinsoku', 'overflowPunct', 'mirrorMargins', 'gutterAtTop', 'defaultTabStop'}
PARAGRAPH_PROPERTIES = {'kinsoku', 'snapToGrid', 'wordWrap', 'autoSpaceDE', 'autoSpaceDN', 'overflowPunct', 'topLinePunct',
    'suppressAutoHyphens', 'keepNext', 'keepLines', 'pageBreakBefore', 'widowControl', 'tabs', 'indent', 'firstLineIndent', 'rightIndent', 'hangingIndent'}
SECTION_PROPERTIES = {'pgBorders', 'pgBorders.top', 'pgBorders.bottom', 'pgBorders.left', 'pgBorders.right', 'pgBorders.offsetFrom',
    'pgBorders.zOrder', 'pgBorders.display', 'vAlign', 'textDirection', 'rtlGutter', 'marginGutter', 'marginHeader', 'marginFooter'}


def reload(package):
    fresh = type(package)(package.path)
    package.parts, package.roots, package.original_trees = fresh.parts, fresh.roots, fresh.original_trees


def native_properties(package, path, kind, properties):
    from .capabilities import check_properties
    module = {'document': 'M05', 'section': 'M05', 'style': 'M03', 'paragraph': 'M03'}[kind]
    check_properties(module, kind, 'set', properties)
    package.save(); OfficeBackend().edit(package.path, path, 'set', kind, properties); reload(package)


def apply(package, target, module, props):
    require_actions()
    from .extensions import _sdk
    operation = props.get('operation')
    if operation == 'theme':
        if set(props) != {'operation', 'properties'}: raise WordError('THEME_PROPERTY_UNSUPPORTED')
        properties = props['properties']
        allowed = {'theme.name', 'theme.colorScheme', 'theme.fontScheme'} | {'theme.color.' + n for n in ('dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink')} | {'theme.font.' + group + '.' + face for group in ('major', 'minor') for face in ('latin', 'eastAsia', 'cs')}
        if not properties or set(properties) - allowed: raise WordError('THEME_PROPERTY_UNSUPPORTED')
        base = {key: value for key, value in properties.items() if key.startswith('theme.color.') or key.startswith('theme.font.') and not key.endswith('.cs')}
        extra = {key: value for key, value in properties.items() if key not in base}
        package.save()
        if base: OfficeBackend().edit(package.path, '/', 'set', 'document', base)
        if extra: _sdk(package.path, target['id'], module, {'operation': 'theme', 'properties': extra})
        reload(package)
        return {'operation': operation, 'properties': properties}
    if operation == 'frame':
        if target['kind'] != 'paragraph': raise WordError('FRAME_PARAGRAPH_REQUIRED')
        if set(props) - {'operation', 'attributes'}: raise WordError('FRAME_PROPERTY_UNSUPPORTED')
        attributes = props.get('attributes', {})
        allowed = {'dropCap', 'lines', 'w', 'h', 'x', 'y', 'hSpace', 'vSpace', 'wrap', 'hAnchor', 'vAnchor', 'hRule', 'xAlign', 'yAlign', 'anchorLock'}
        if not attributes or set(attributes) - allowed: raise WordError('FRAME_PROPERTY_UNSUPPORTED')
        package.save(); result = _sdk(package.path, target['id'], module, props); reload(package); return result
    if operation == 'embed_fonts':
        if set(props) - {'operation', 'fonts'}: raise WordError('FONT_EMBED_PROPERTY_UNSUPPORTED')
        from fontTools.ttLib import TTFont
        fonts, records = [], []
        with tempfile.TemporaryDirectory() as temporary:
            for index, entry in enumerate(props.get('fonts', [])):
                if set(entry) - {'family', 'file', 'index', 'variant', 'redistributable'}: raise WordError('FONT_EMBED_PROPERTY_UNSUPPORTED')
                if entry.get('redistributable') is not True: raise WordError('FONT_DISTRIBUTION_DECLARATION_REQUIRED')
                file = Path(entry['file']).resolve()
                with TTFont(file, fontNumber=entry.get('index', 0)) as font:
                    flags = int(font['OS/2'].fsType) if 'OS/2' in font else 0
                    if flags & (0x0002 | 0x0200) or flags & 0x0004 and not flags & 0x0008: raise WordError('FONT_EMBEDDING_RESTRICTED', entry['family'])
                    names = {n.toUnicode().casefold() for n in font['name'].names if n.nameID in (1, 4, 6, 16)}
                    if entry['family'].casefold() not in names: raise WordError('FONT_FAMILY_MISMATCH', entry['family'])
                    output = Path(temporary) / (str(index) + '.ttf'); font.save(output)
                fonts.append({'family': entry['family'], 'file': str(output), 'variant': entry.get('variant', 'regular')})
                records.append({'family': entry['family'], 'source_sha256': digest(file), 'embedded_sha256': digest(output), 'fsType': flags, 'variant': entry.get('variant', 'regular')})
            if not fonts: raise WordError('FONT_EMBED_INPUT_REQUIRED')
            package.save(); result = _sdk(package.path, target['id'], module, {'operation': operation, 'fonts': fonts}); reload(package)
        result['sources'] = records; return result
    raise WordError('TYPOGRAPHY_EXTENSION_UNSUPPORTED', operation)
