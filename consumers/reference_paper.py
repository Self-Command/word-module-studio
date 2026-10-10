"""MIT consumer adapter: policy becomes TemplateSpec; engine contains no journal switch."""
from copy import deepcopy
from pathlib import Path
from word_module_studio.runtime import WordError, require_actions
from word_module_studio.templates import build
from word_module_studio.compose import compose


def template_spec(identity, policy, fonts, *, variant='front'):
    require_actions()
    if set(fonts) < {'latin', 'cjk', 'math'}: raise WordError('EXPLICIT_FONT_SCHEME_REQUIRED')
    page_policy = policy['page']
    width = page_policy.get('width_cm', 21); height = page_policy.get('height_cm', 29.7)
    def twips(value): return round(value * 1440 / 2.54)
    page = {'width_twips': twips(width), 'height_twips': twips(height),
        'margins_twips': [twips(page_policy['margin_cm'][s]) for s in ('top', 'right', 'bottom', 'left')]}
    styles = {'Normal': {'size_pt': policy['body_size_pt'], 'line_spacing': 1.0},
        'Title': {'size_pt': 16, 'bold': True, 'alignment': 'center', 'keep_next': True},
        'Author': {'size_pt': 10, 'alignment': 'center'}, 'Abstract': {'size_pt': 9}, 'Keywords': {'size_pt': 9},
        'Caption': {'size_pt': 9, 'alignment': 'center', 'keep_next': False}}
    for level in range(1, 5): styles['Heading' + str(level)] = {'size_pt': 12 if level == 1 else 10, 'bold': True, 'keep_next': True}
    roles = {'title': 'Title', 'authors': 'Author', 'affiliation': 'Author', 'abstract': 'Abstract', 'keywords': 'Keywords'}
    def slots(language): return [{'key': key + '_' + language, 'style': role} for key, role in roles.items()
        if key in policy.get('front_roles', list(roles)) and not (policy.get('anonymous') and key in ('authors', 'affiliation'))]
    languages = policy.get('metadata_languages', ['zh', 'en'])
    move_en_to_end = variant == 'end' and len(languages) > 1 and 'en' in languages
    front = [slot for language in languages if not move_en_to_end or language != 'en' for slot in slots(language)]
    regions = [{'id': 'front', 'page': deepcopy(page), 'columns': 1, 'gap_twips': twips(page_policy.get('column_spacing_cm', .6)), 'slots': front},
        {'id': 'body', 'page': deepcopy(page), 'columns': policy.get('body_columns', 2), 'gap_twips': twips(page_policy.get('column_spacing_cm', .6)),
            'break': 'nextPage' if policy.get('front_separate_page') else 'continuous'}]
    if move_en_to_end:
        regions.append({'id': 'end', 'page': deepcopy(page), 'columns': 1, 'gap_twips': 0, 'break': 'continuous', 'slots': slots('en')})
    if policy.get('page_numbers'): regions[0].update(footer='{{PAGE}}', page_start=1, page_format='decimal')
    return {'schema_version': 1, 'id': identity['id'], 'version': identity['version'] + '-' + variant,
        'fonts': dict(fonts), 'regions': regions, 'styles': styles, 'captions': policy['captions'],
        'equations': {'numbering': policy.get('equation_numbering', 'preserve'), 'number_width_twips': 600, 'long_formula': 'safe_wrap'}}


def export(markdown, definition, fonts, output, *, metadata, variant='front', resources=()):
    require_actions()
    spec = template_spec(definition, definition['policy'], fonts, variant=variant)
    manifest = build(spec, Path(output).parent / ('master-' + definition['id'] + '-' + variant))
    return compose(markdown, manifest, output, region='body', resources=resources, data=metadata)
