"""System-Python UNO client for the pinned LibreOffice compatibility renderer."""
import os
import json
from pathlib import Path
import sys
import time
import uno
import zipfile
import shutil
import re
from xml.etree import ElementTree
from com.sun.star.beans import PropertyValue

if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'): raise RuntimeError('CLOUD_ONLY')


def prop(name, value):
    result = PropertyValue(); result.Name = name; result.Value = value; return result


source, output, port = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
source_math = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else []
context = uno.getComponentContext()
resolver = context.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', context)
connection = None
for attempt in range(30):
    try:
        connection = resolver.resolve('uno:socket,host=127.0.0.1,port=' + port + ';urp;StarOffice.ComponentContext')
        break
    except Exception: time.sleep(.3)
if connection is None: raise RuntimeError('RENDERER_CONNECTION_FAILED')
desktop = connection.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', connection)
document = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(source)), '_blank', 0,
    (prop('Hidden', True), prop('ReadOnly', False), prop('UpdateDocMode', 3),
     prop('MacroExecutionMode', uno.getConstantByName('com.sun.star.document.MacroExecMode.NEVER_EXECUTE'))))
if document is None: raise RuntimeError('RENDERER_LOAD_FAILED')
try:
    # The DOCX mathFont is otherwise lost when Writer imports OMML into
    # StarMath. Apply its explicit family to the compatibility proof only.
    math_font = None
    with zipfile.ZipFile(source) as package:
        settings = ElementTree.fromstring(package.read('word/settings.xml'))
        namespace = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
        node = settings.find(namespace + 'mathPr/' + namespace + 'mathFont')
        if node is not None: math_font = node.get(namespace + 'val')
    formula_fonts = []
    embedded = document.getEmbeddedObjects()
    font_properties = ('FontNameVariables', 'FontNameFunctions', 'FontNameNumbers', 'FontNameText',
        'CustomFontNameSerif', 'CustomFontNameSans', 'CustomFontNameFixed')
    for index in range(embedded.Count):
        item = embedded.getByIndex(index); model = item.Model
        if not model.supportsService('com.sun.star.formula.FormulaProperties'): continue
        source_properties = source_math[len(formula_fonts)] if len(formula_fonts) < len(source_math) else {}
        imported_height = model.BaseFontHeight
        imported_formula = model.Formula
        # Writer imports a native matrix cell beginning with a relation as
        # `# = 1`; StarMath requires a left operand. An empty group supplies
        # that syntactic operand without adding a visible mathematical symbol.
        compatible_formula = re.sub(r'([#{]\s*)(?=(?:=|≤|≥|≠|≈|<|>)\s)', r'\1{} ', imported_formula)
        compatibility_changes = []
        if compatible_formula != imported_formula:
            compatibility_changes.append('Empty StarMath operand before a leading matrix-cell relation')
            model.Formula = compatible_formula
        if math_font:
            model.setPropertyValues(font_properties, tuple(math_font for _ in font_properties))
            # StarMath's imported per-face sizes can survive a BaseFontHeight
            # change. Its native size command expresses the source point size
            # explicitly and recalculates the visual area in SmModel itself.
            # Updating ExtendedControl synchronously can deadlock Writer; do not
            # request it or impose a separately measured frame size.
            size_pt = source_properties.get('size_pt', imported_height)
            model.Formula = 'size ' + str(size_pt) + ' {' + compatible_formula + '}'
        formula_fonts.append({'index': index, 'requested': math_font, 'formula': model.Formula,
            'source_order_candidate': source_properties, 'imported_base_height_pt': imported_height,
            'base_font_height_pt': model.BaseFontHeight,
            'imported_formula': imported_formula, 'explicit_size_pt': size_pt if math_font else None,
            'compatibility_changes': compatibility_changes,
            'object_width_pt': item.Size.Width * 72 / 2540, 'object_height_pt': item.Size.Height * 72 / 2540,
            'actual': {name: model.getPropertyValue(name) for name in font_properties}})
    for iteration in range(3):
        document.TextFields.refresh()
        for index in range(document.DocumentIndexes.Count): document.DocumentIndexes.getByIndex(index).update()
        document.TextFields.refresh()
        pass_file = output.with_name(output.stem + '.pass-' + str(iteration) + '.pdf')
        document.storeToURL(uno.systemPathToFileUrl(str(pass_file)), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
    document.TextFields.refresh()
    for index in range(document.DocumentIndexes.Count): document.DocumentIndexes.getByIndex(index).update()
    document.TextFields.refresh()
    layout = {'paragraphs': [], 'tables': [], 'frames': [], 'shapes': [], 'formula_fonts': formula_fonts}
    cursor = document.CurrentController.ViewCursor
    enumeration = document.Text.createEnumeration()
    while enumeration.hasMoreElements():
        item = enumeration.nextElement()
        if item.supportsService('com.sun.star.text.Paragraph'):
            cursor.gotoRange(item.Start, False)
            style = document.StyleFamilies.getByName('PageStyles').getByName(cursor.PageStyleName)
            columns = style.TextColumns.getColumns()
            page = {'width_pt': style.Width * 72 / 2540, 'height_pt': style.Height * 72 / 2540,
                'left_pt': style.LeftMargin * 72 / 2540, 'right_pt': style.RightMargin * 72 / 2540,
                'top_pt': style.TopMargin * 72 / 2540, 'bottom_pt': style.BottomMargin * 72 / 2540,
                'columns': [{'width': c.Width, 'left_pt': c.LeftMargin * 72 / 2540,
                    'right_pt': c.RightMargin * 72 / 2540} for c in columns]}
            drop_cap = item.DropCapFormat
            layout['paragraphs'].append({'text': item.String, 'page': cursor.Page,
                'x_pt': cursor.Position.X * 72 / 2540 + page['left_pt'],
                'y_pt': cursor.Position.Y * 72 / 2540 + page['top_pt'], 'page_geometry': page,
                'drop_cap': {'lines': drop_cap.Lines, 'count': drop_cap.Count, 'distance_mm100': drop_cap.Distance}})
    for name in document.TextTables.ElementNames:
        table = document.TextTables.getByName(name)
        rows = []
        try:
            for index in range(table.Rows.Count):
                cell = table.getCellByPosition(0, index); cursor.gotoRange(cell.Start, False)
                style = document.StyleFamilies.getByName('PageStyles').getByName(cursor.PageStyleName)
                rows.append({'row': index, 'page': cursor.Page, 'x_pt': (cursor.Position.X + style.LeftMargin) * 72 / 2540,
                    'y_pt': (cursor.Position.Y + style.TopMargin) * 72 / 2540, 'text': cell.String})
        except Exception as exc:
            rows.append({'diagnostic': 'Merged table row positions need manual review: ' + str(exc)})
        layout['tables'].append({'name': name, 'rows': rows})
    for name in document.TextFrames.ElementNames:
        frame = document.TextFrames.getByName(name)
        cursor.gotoRange(frame.Anchor, False)
        left = getattr(frame, 'LeftBorderDistance', 0) * 72 / 2540
        right = getattr(frame, 'RightBorderDistance', 0) * 72 / 2540
        layout['frames'].append({'name': name, 'text': frame.String, 'page': cursor.Page,
            'width_pt': frame.Size.Width * 72 / 2540, 'height_pt': frame.Size.Height * 72 / 2540,
            'left_inset_pt': left, 'right_inset_pt': right})
    draw = document.DrawPage
    for index in range(draw.Count):
        shape = draw.getByIndex(index)
        record = {'index': index, 'kind': shape.ShapeType,
            'width_pt': shape.Size.Width * 72 / 2540, 'height_pt': shape.Size.Height * 72 / 2540}
        try:
            position = shape.getPosition()
            record.update(x_pt=position.X * 72 / 2540, y_pt=position.Y * 72 / 2540)
        except Exception:
            record['position_requires_visual_review'] = True
        try:
            cursor.gotoRange(shape.Anchor, False); record['page'] = cursor.Page
        except Exception: record['page'] = None
        layout['shapes'].append(record)
    output.with_suffix('.layout.json').write_text(json.dumps(layout, ensure_ascii=False, indent=2))
    shutil.copyfile(pass_file, output)
    # Compatibility copy is diagnostic only: never replace the original editable DOCX.
    refreshed = output.with_suffix('.refreshed.docx')
    document.storeToURL(uno.systemPathToFileUrl(str(refreshed)), (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)))
finally:
    document.close(True)
    desktop.terminate()
