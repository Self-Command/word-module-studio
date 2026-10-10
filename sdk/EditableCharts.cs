using System.Globalization;
using System.Xml.Linq;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;

// The workbook is a real SpreadsheetML package, linked by c:externalData.
// Caches and cell formulas are updated together; editable data is never inferred
// merely from a cached image or a chart part's existence.
internal static class EditableCharts {
    static readonly XNamespace C = "http://schemas.openxmlformats.org/drawingml/2006/chart";
    static readonly XNamespace R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

    public static void Synchronize(ChartPart chart) {
        XDocument xml;
        using (var input = chart.GetStream()) xml = XDocument.Load(input);
        var series = xml.Descendants(C + "ser").ToArray();
        if (series.Length == 0) throw new InvalidOperationException("CHART_SERIES_MISSING");
        var columns = new List<(string Name, bool Numeric, string[] Values)>();
        foreach (var ser in series) {
            var x = ser.Element(C + "cat") ?? ser.Element(C + "xVal");
            var y = ser.Element(C + "val") ?? ser.Element(C + "yVal");
            if (x == null || y == null) throw new InvalidOperationException("CHART_DATA_MISSING");
            var ys = Points(y);
            var xs = Points(x);
            var numeric = x.Descendants(C + "numCache").Any() || x.Descendants(C + "numLit").Any();
            if (xs.Length != ys.Length || xs.Length == 0) throw new InvalidOperationException("CHART_DATA_LENGTH_MISMATCH");
            var title = ser.Element(C + "tx");
            var name = title?.Descendants(C + "v").FirstOrDefault()?.Value ?? "Series " + (columns.Count / 2 + 1);
            var xcol = ColumnName(columns.Count + 1); columns.Add(("Category", numeric, xs));
            var ycol = ColumnName(columns.Count + 1); columns.Add((name, true, ys));
            Bind(x, numeric, $"Sheet1!${xcol}$2:${xcol}${xs.Length + 1}");
            Bind(y, true, $"Sheet1!${ycol}$2:${ycol}${ys.Length + 1}");
            if (title == null) { title = new XElement(C + "tx"); ser.Element(C + "order")!.AddAfterSelf(title); }
            title.ReplaceNodes(new XElement(C + "strRef", new XElement(C + "f", $"Sheet1!${ycol}$1"),
                new XElement(C + "strCache", new XElement(C + "ptCount", new XAttribute("val", 1)),
                    new XElement(C + "pt", new XAttribute("idx", 0), new XElement(C + "v", name)))));
        }
        using var buffer = new MemoryStream();
        using (var workbook = SpreadsheetDocument.Create(buffer, DocumentFormat.OpenXml.SpreadsheetDocumentType.Workbook, true)) {
            var main = workbook.AddWorkbookPart(); main.Workbook = new Workbook();
            var sheet = main.AddNewPart<WorksheetPart>();
            var data = new SheetData(); sheet.Worksheet = new Worksheet(data);
            var header = new Row { RowIndex = 1 };
            for (var i = 0; i < columns.Count; i++) header.Append(TextCell(ColumnName(i + 1) + "1", columns[i].Name));
            data.Append(header);
            for (var index = 0; index < columns.Max(c => c.Values.Length); index++) {
                var row = new Row { RowIndex = (uint)index + 2 };
                for (var col = 0; col < columns.Count; col++) {
                    if (index >= columns[col].Values.Length) continue;
                    var address = ColumnName(col + 1) + (index + 2);
                    var value = columns[col].Values[index];
                    if (columns[col].Numeric) {
                        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out _))
                            throw new InvalidOperationException("CHART_NON_NUMERIC_VALUE");
                        row.Append(new Cell { CellReference = address, DataType = CellValues.Number, CellValue = new CellValue(value) });
                    } else row.Append(TextCell(address, value));
                }
                data.Append(row);
            }
            main.Workbook.Append(new Sheets(new Sheet { Id = main.GetIdOfPart(sheet), SheetId = 1, Name = "Sheet1" }));
            sheet.Worksheet.Save(); main.Workbook.Save();
        }
        var external = xml.Root!.Element(C + "externalData");
        EmbeddedPackagePart embedded;
        var oldId = (string?)external?.Attribute(R + "id");
        if (oldId != null && chart.GetPartById(oldId) is EmbeddedPackagePart existing) embedded = existing;
        else embedded = chart.AddEmbeddedPackagePart("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        buffer.Position = 0; embedded.FeedData(buffer);
        if (external == null) {
            external = new XElement(C + "externalData");
            var following = xml.Root.Elements().FirstOrDefault(n => n.Name == C + "printSettings" || n.Name == C + "userShapes" || n.Name == C + "extLst");
            if (following == null) xml.Root.Add(external); else following.AddBeforeSelf(external);
        }
        external.SetAttributeValue(R + "id", chart.GetIdOfPart(embedded));
        external.ReplaceNodes(new XElement(C + "autoUpdate", new XAttribute("val", "0")));
        using var output = chart.GetStream(FileMode.Create, FileAccess.Write); xml.Save(output);
    }

    static string[] Points(XElement container) => container.Descendants(C + "pt")
        .OrderBy(p => (int?)p.Attribute("idx") ?? 0).Select(p => p.Element(C + "v")?.Value ?? "").ToArray();
    static void Bind(XElement container, bool numeric, string formula) {
        var cache = container.Descendants(C + (numeric ? "numCache" : "strCache")).FirstOrDefault()
            ?? container.Descendants(C + (numeric ? "numLit" : "strLit")).FirstOrDefault()
            ?? throw new InvalidOperationException("CHART_CACHE_MISSING");
        cache = new XElement(cache); cache.Name = C + (numeric ? "numCache" : "strCache");
        container.ReplaceNodes(new XElement(C + (numeric ? "numRef" : "strRef"), new XElement(C + "f", formula), cache));
    }
    static Cell TextCell(string address, string value) => new Cell {
        CellReference = address, DataType = CellValues.InlineString, InlineString = new InlineString(new Text(value))
    };
    static string ColumnName(int number) {
        var result = ""; while (number > 0) { number--; result = (char)('A' + number % 26) + result; number /= 26; }
        return result;
    }
}
