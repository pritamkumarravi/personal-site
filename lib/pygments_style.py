"""Pygments style matched to the site palette (see spec §3.1)."""

from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Whitespace,
)


class SiteStyle(Style):
    name = "pritamravi"

    background_color = "#19191F"  # Surface
    highlight_color = "#222129"  # Elevated

    styles = {
        Whitespace: "#65616C",
        Punctuation: "#92909A",
        Comment: "italic #65616C",
        Comment.Preproc: "#D8A657",
        Comment.Special: "italic #D8A657",
        Keyword: "#B4A3E6",
        Keyword.Constant: "#D8A657",
        Keyword.Declaration: "#B4A3E6",
        Keyword.Type: "#D8A657",
        Operator: "#92909A",
        Operator.Word: "#B4A3E6",
        Name.Builtin: "#A3BE8C",
        Name.Builtin.Pseudo: "#A3BE8C",
        Name.Function: "bold #E6E1D6",
        Name.Class: "bold #E6E1D6",
        Name.Decorator: "#D8A657",
        Name.Tag: "#B4A3E6",
        Name.Attribute: "#A3BE8C",
        Name.Constant: "#D8A657",
        Name.Variable: "#E6E1D6",
        Name.Label: "#D8A657",
        Number: "#D8A657",
        String: "#A3BE8C",
        String.Doc: "italic #65616C",
        String.Interpol: "#D8A657",
        String.Escape: "#D8A657",
        Generic.Heading: "bold #E6E1D6",
        Generic.Subheading: "#B4A3E6",
        Generic.Emph: "italic",
        Generic.Strong: "bold",
        Error: "#D8A657 bg:#2c2013",
    }
