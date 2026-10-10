"""System-Python UNO client for the pinned LibreOffice compatibility renderer."""
import os
import json
from pathlib import Path
import sys
import time
import uno
from com.sun.star.beans import PropertyValue

if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'): raise RuntimeError('CLOUD_ONLY')


def prop(name, value):
    result = PropertyValue(); result.Name = name; result.Value = value; return result


source, output, port = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
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
    document.TextFields.refresh()
    for index in range(document.DocumentIndexes.Count): document.DocumentIndexes.getByIndex(index).update()
    document.TextFields.refresh()
    layout = {'paragraphs': [], 'tables': []}
    cursor = document.CurrentController.ViewCursor
    enumeration = document.Text.createEnumeration()
    while enumeration.hasMoreElements():
        item = enumeration.nextElement()
        if item.supportsService('com.sun.star.text.Paragraph'):
            cursor.gotoRange(item.Start, False)
            layout['paragraphs'].append({'text': item.String, 'page': cursor.Page,
                'x_pt': cursor.Position.X * 72 / 2540, 'y_pt': cursor.Position.Y * 72 / 2540})
    for name in document.TextTables.ElementNames:
        table = document.TextTables.getByName(name)
        rows = []
        try:
            for index in range(table.Rows.Count):
                cell = table.getCellByPosition(0, index); cursor.gotoRange(cell.Start, False)
                rows.append({'row': index, 'page': cursor.Page, 'x_pt': cursor.Position.X * 72 / 2540,
                    'y_pt': cursor.Position.Y * 72 / 2540, 'text': cell.String})
        except Exception as exc:
            rows.append({'diagnostic': 'Merged table row positions need manual review: ' + str(exc)})
        layout['tables'].append({'name': name, 'rows': rows})
    output.with_suffix('.layout.json').write_text(json.dumps(layout, ensure_ascii=False, indent=2))
    document.storeToURL(uno.systemPathToFileUrl(str(output)), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
    # Compatibility copy is diagnostic only: never replace the original editable DOCX.
    refreshed = output.with_suffix('.refreshed.docx')
    document.storeToURL(uno.systemPathToFileUrl(str(refreshed)), (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)))
finally:
    document.close(True)
    desktop.terminate()
