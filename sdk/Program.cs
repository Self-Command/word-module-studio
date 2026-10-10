using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
using DocumentFormat.OpenXml.Wordprocessing;

if (Environment.GetEnvironmentVariable("GITHUB_ACTIONS") != "true" ||
    String.IsNullOrEmpty(Environment.GetEnvironmentVariable("GITHUB_RUN_ID")))
    throw new InvalidOperationException("CLOUD_ONLY");
if (args.Length < 2 || (args[0] != "validate" && args[0] != "apply"))
    throw new ArgumentException("Usage: WordSdk validate file.docx | apply file.docx request.json");
using var document = WordprocessingDocument.Open(args[1], args[0] == "apply");
if (args[0] == "apply") {
    using var request = JsonDocument.Parse(File.ReadAllText(args[2]));
    var requestRoot = request.RootElement;
    var properties = requestRoot.GetProperty("props");
    var operation = properties.GetProperty("operation").GetString();
    if (operation == "unequal_columns") {
        var targetId = requestRoot.GetProperty("target").GetString();
        var target = document.MainDocumentPart!.Document.Descendants<SectionProperties>()
            .Single(e => e.GetAttribute("id", "urn:word-module-studio:objects:v1").Value == targetId);
        var widths = properties.GetProperty("widths_twips").EnumerateArray().Select(v => v.GetInt32()).ToArray();
        var gap = properties.GetProperty("gap_twips").GetInt32();
        if (widths.Length < 1 || widths.Any(w => w <= 0) || gap < 0) throw new ArgumentException("INVALID_COLUMN_WIDTHS");
        var columns = new Columns { EqualWidth = false, ColumnCount = (short)widths.Length, Space = gap.ToString() };
        foreach (var width in widths) columns.Append(new Column { Width = width.ToString(), Space = gap.ToString() });
        var old = target.GetFirstChild<Columns>();
        if (old != null) target.ReplaceChild(columns, old); else target.AddChild(columns, true);
    } else if (operation == "sync_charts") {
        var paths = properties.GetProperty("parts").EnumerateArray().Select(p => "/" + p.GetString()!.TrimStart('/')).ToHashSet();
        foreach (var chart in document.MainDocumentPart!.ChartParts.Where(p => paths.Contains(p.Uri.ToString())))
            EditableCharts.Synchronize(chart);
    } else if (operation == "convert_notes") {
        var direction = properties.GetProperty("to").GetString();
        var main = document.MainDocumentPart!;
        if (direction == "endnote") {
            var source = main.FootnotesPart ?? throw new InvalidOperationException("FOOTNOTES_MISSING");
            if (main.EndnotesPart != null) throw new InvalidOperationException("ENDNOTES_ALREADY_EXIST");
            var destination = main.AddNewPart<EndnotesPart>(); destination.Endnotes = new Endnotes();
            foreach (var note in source.Footnotes!.Elements<Footnote>()) {
                var converted = new Endnote { Id = note.Id, Type = note.Type };
                foreach (var content in note.ChildElements) converted.Append(content.CloneNode(true));
                foreach (var mark in converted.Descendants<FootnoteReferenceMark>().ToArray())
                    mark.Parent!.ReplaceChild(new EndnoteReferenceMark(), mark);
                destination.Endnotes.Append(converted);
            }
            foreach (var reference in main.Document.Descendants<FootnoteReference>().ToArray())
                reference.Parent!.ReplaceChild(new EndnoteReference { Id = reference.Id }, reference);
            CopyNoteRelationships(source, destination);
            destination.Endnotes.Save(); main.DeletePart(source);
        } else if (direction == "footnote") {
            var source = main.EndnotesPart ?? throw new InvalidOperationException("ENDNOTES_MISSING");
            if (main.FootnotesPart != null) throw new InvalidOperationException("FOOTNOTES_ALREADY_EXIST");
            var destination = main.AddNewPart<FootnotesPart>(); destination.Footnotes = new Footnotes();
            foreach (var note in source.Endnotes!.Elements<Endnote>()) {
                var converted = new Footnote { Id = note.Id, Type = note.Type };
                foreach (var content in note.ChildElements) converted.Append(content.CloneNode(true));
                foreach (var mark in converted.Descendants<EndnoteReferenceMark>().ToArray())
                    mark.Parent!.ReplaceChild(new FootnoteReferenceMark(), mark);
                destination.Footnotes.Append(converted);
            }
            foreach (var reference in main.Document.Descendants<EndnoteReference>().ToArray())
                reference.Parent!.ReplaceChild(new FootnoteReference { Id = reference.Id }, reference);
            CopyNoteRelationships(source, destination);
            destination.Footnotes.Save(); main.DeletePart(source);
        } else throw new ArgumentException("INVALID_NOTE_CONVERSION");
    } else if (operation == "frame" || operation == "embed_fonts" || operation == "theme") {
        var result = LayoutFeatures.Apply(document, requestRoot.GetProperty("target").GetString(), properties);
        document.MainDocumentPart!.Document.Save();
        Console.WriteLine(JsonSerializer.Serialize(result));
        return 0;
    } else throw new ArgumentException("SDK_EXTENSION_UNSUPPORTED");
    document.MainDocumentPart!.Document.Save();
    Console.WriteLine(JsonSerializer.Serialize(new { operation, applied = true }));
    return 0;
}
var validator = new OpenXmlValidator(FileFormatVersions.Office2021);
var errors = validator.Validate(document).Select(e => new {
    id = e.Id, description = e.Description, part = e.Part?.Uri.ToString(), path = e.Path?.XPath
}).ToList();
Console.WriteLine(JsonSerializer.Serialize(new { version = "3.4.1", target = "Office2021", errors }));
return errors.Count == 0 ? 0 : 2;

static void CopyNoteRelationships(OpenXmlPart source, OpenXmlPart destination) {
    foreach (var part in source.Parts) destination.AddPart(part.OpenXmlPart, part.RelationshipId);
    foreach (var rel in source.HyperlinkRelationships) destination.AddHyperlinkRelationship(rel.Uri, rel.IsExternal, rel.Id);
    foreach (var rel in source.ExternalRelationships) destination.AddExternalRelationship(rel.RelationshipType, rel.Uri, rel.Id);
}
