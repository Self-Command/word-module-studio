"""Known Word property order; extension code does not append blindly."""
from lxml import etree as E
from .package import W

ORDER = {
 'sectPr': 'headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange'.split(),
 'pPr': 'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'.split(),
 'tblPr': 'tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange'.split(),
 'trPr': 'cnfStyle divId gridBefore gridAfter wBefore wAfter cantSplit trHeight tblHeader tblCellSpacing jc hidden ins del trPrChange'.split(),
 'tcPr': 'cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark headers cellIns cellDel cellMerge tcPrChange'.split(),
 'sdtPr': 'rPr alias lock placeholder showingPlcHdr dataBinding temporary id tag color appearance webExtensionLinked webExtensionCreated equation comboBox date docPartObj docPartList dropDownList picture richText text citation group bibliographic entityPicker checkbox repeatingSection repeatingSectionItem'.split()
}


def order_properties(root):
    for element in root.iter():
        names = ORDER.get(E.QName(element).localname)
        if names is None: continue
        ranks = {name: index for index, name in enumerate(names)}
        children = list(element)
        element[:] = sorted(children, key=lambda node: ranks.get(E.QName(node).localname, len(names)))
