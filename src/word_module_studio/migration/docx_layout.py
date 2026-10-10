from lxml import etree
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def math_width_pt(element, size, metrics=None):
    """Conservative OMML width estimate for routing, not mathematical rewriting.

    Fractions stack, matrices/arrays take their widest row and scripts use
    smaller text.  The rendered cloud proof remains the acceptance authority.
    """
    local = etree.QName(element).localname
    if local.endswith("Pr"):
        return 0
    if local == "t":
        if metrics is not None:
            return sum(size*(metrics["cjk" if 0x3400<=ord(c)<=0x9fff else "math"].get(c,
                            .28 if c.isspace() else .70)*1.08) for c in element.text or "")
        return sum(size * (1.15 if ord(c) > 0x2fff else .28 if c.isspace() else .70) for c in element.text or "")
    children = [c for c in element if not etree.QName(c).localname.endswith("Pr")]
    measured = [(etree.QName(c).localname, math_width_pt(c, size,metrics) if metrics is not None else math_width_pt(c,size)) for c in children]
    widths = dict(measured)
    values = [width for _,width in measured]
    if local == "r":
        # TeX/OMML place real glue around relation and binary operators.
        # Glyph advances alone miss e.g. both sides of >= and membership.
        # Reserve normal math-style glue (5/4 mu on each side, 3 mu after
        # punctuation); leading/unary operators may use less in a renderer.
        text="".join(c.text or "" for c in element.findall(M+"t"))
        relation=set("=<>≤≥≠≈≃≡∈∉⊂⊃⊆⊇→↔⇒⇔∝")
        binary=set("+−×÷∧∨∪∩")
        glue=sum(10/18 if char in relation else 8/18 if char in binary else 3/18 if char in ",;" else 0 for char in text)
        return sum(values)+size*glue
    if local == "f":
        return max(widths.get("num", 0), widths.get("den", 0)) + size * .4
    if local in ("sSub", "sSup", "sSubSup"):
        return widths.get("e", 0) + .75 * max(widths.get("sub", 0), widths.get("sup", 0))
    if local in ("eqArr", "m"):
        return max(values, default=0)
    if local == "mr":
        return sum(values) + max(0, len(children) - 1) * size
    if local == "nary":
        return widths.get("e", 0) + max(size * 1.8, .75 * max(widths.get("sub", 0), widths.get("sup", 0)))
    if local in ("limLow", "limUpp"):
        return max(widths.get("e", 0), .75 * widths.get("lim", 0))
    if local in ("d", "borderBox"):
        return sum(values) + size * 1.3
    return sum(values)


