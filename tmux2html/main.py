# coding: utf8
from __future__ import print_function, unicode_literals

import re
import argparse
from string import Template

from . import color, utils

try:
    from html import escape
except ImportError:
    from cgi import escape


classname = 'tmux-html'
tpl = Template('''
<!doctype html>
<head>
  <meta charset="utf-8">
  <title>tmux</title>
  <style>
    body {
      margin: 0;
      padding: 0;
    }
    .$prefix .pane {
      display: inline-block;
    }
    .$prefix pre {
      font-size: 10pt;
      margin: 0;
      padding: 0;
    }
    .$prefix .u {
      position: relative;
      display: inline-block;
      font-size: inherit;
      color: inherit;
      background-color: transparent;
    }
    .$prefix .u:after {
      content: attr(data-glyph);
      display: block;
      position: absolute;
      top: 0;
      left: 0;
    }
    .$prefix .v {
      display: inline-flex;
      flex-direction: column;
      flex-wrap: nowrap;
    }
    .$prefix .h {
      display: inline-flex;
      flex-direction: row;
      flex-wrap: nowrap;
    }
    $css
  </style>
</head>
<body>
<div class="$prefix">$panes</div>
</body>
'''.strip())


font_stack = (
    'Anonymice Powerline',
    'Arimo for Powerline',
    'Aurulent Sans Mono',
    'Bitstream Vera Sans Mono',
    'Cousine for Powerline',
    'DejaVu Sans Mono for Powerline',
    'Droid Sans Mono Dotted for Powerline',
    'Droid Sans Mono Slashed for Powerline',
    'Droid Sans Mono for Powerline',
    'Fira Mono Medium for Powerline',
    'Fira Mono for Powerline',
    'Fura Mono Medium for Powerline',
    'Fura Mono for Powerline',
    'Hack',
    'Heavy Data',
    'Hurmit',
    'IBM 3270',
    'IBM 3270 Narrow',
    'Inconsolata for Powerline',
    'Inconsolata-dz for Powerline',
    'Inconsolata-g for Powerline',
    'Knack',
    'Lekton',
    'Literation Mono Powerline',
    'M+ 1m',
    'Meslo LG L DZ for Powerline',
    'Meslo LG L for Powerline',
    'Meslo LG M DZ for Powerline',
    'Meslo LG M for Powerline',
    'Meslo LG S DZ for Powerline',
    'Meslo LG S for Powerline',
    'ProFontWindows',
    'ProggyCleanTT',
    'ProggyCleanTT CE',
    'Roboto Mono Light for Powerline',
    'Roboto Mono Medium for Powerline',
    'Roboto Mono Thin for Powerline',
    'Roboto Mono for Powerline',
    'Sauce Code Powerline',
    'Sauce Code Pro',
    'Sauce Code Pro Black',
    'Sauce Code Pro ExtraLight',
    'Sauce Code Pro Light',
    'Sauce Code Pro Medium',
    'Sauce Code Pro Semibold',
    'Source Code Pro Black for Powerline',
    'Source Code Pro ExtraLight for Powerline',
    'Source Code Pro Light for Powerline',
    'Source Code Pro Medium for Powerline',
    'Source Code Pro Semibold for Powerline',
    'Symbol Neu for Powerline',
    'Tinos for Powerline',
    'Ubuntu Mono for Powerline',
    'Ubuntu Mono derivative Powerlin',
    'Ubuntu Mono derivative Powerline',
    'monofur for Powerline',
)


class Renderer(object):
    opened = 0
    chunks = []
    css = {}
    esc_style = []

    def __init__(self, fg=(0xfa, 0xfa, 0xfa), bg=0):
        self.default_fg = fg
        self.default_bg = bg

    def rgbhex(self, c, style=None):
        """Converts a color to hex RGB."""
        if not c:
            return 'none'
        if isinstance(c, int):
            c = color.term_to_rgb(c, style)
        return '#{:02x}{:02x}{:02x}'.format(*c)

    def update_css(self, prefix, color_code):
        """Updates the CSS with a color."""
        if color_code is None:
            return ''

        if prefix == 'f':
            style = 'color'
        else:
            style = 'background-color'

        if isinstance(color_code, int):
            if prefix == 'f' and 1 in self.esc_style and color_code < 8:
                color_code += 8
            key = '{0}{1:d}'.format(prefix, color_code)
        else:
            key = '{0}-rgb_{1}'.format(prefix, '_'.join(map(str, color_code)))

        self.css[key] = '{0}: {1};'.format(style, self.rgbhex(color_code,
                                                              self.esc_style))
        return key

    def render_css(self):
        """Render stylesheet.

        If an item is a list or tuple, it is joined.
        """
        out = ''
        ctx = {
            'fonts': ','.join('"{}"'.format(x) for x in font_stack),
            'fg': self.rgbhex(self.default_fg),
            'bg': self.rgbhex(self.default_bg),
        }
        out = ('div.{prefix} pre {{font-family:{fonts},monospace;'
               'background-color:{bg};}}'
               'div.{prefix} pre span {{color:{fg};'
               'background-color:{bg};}}'
               ).format(prefix=classname, **ctx)

        for k, v in self.css.items():
            if isinstance(v, (tuple, list)):
                style = ';'.join(v)
            else:
                style = v
            out += 'div.{prefix} pre span.{cls} {{{style};}}' \
                .format(prefix=classname, cls=k, style=style)
        return out

    def reset_css(self):
        """Reset the CSS to the default state."""
        self.css = {
            'su': 'text-decoration:underline',
            'si': 'font-style:italic',
            'sb': 'font-weight:bold',
            'ns': [
                '-webkit-user-select:none',
                '-moz-user-select:none',
                '-ms-user-select:none',
                'user-select:none',
            ],
        }

    def _style_classes(self, styles):
        """Set an equivalent CSS style."""
        out = []
        if 1 in styles and 22 not in styles:
            out.append('sb')
        if 3 in styles and 23 not in styles:
            out.append('si')
        if 4 in styles and 24 not in styles:
            out.append('su')
        return out

    def open(self, fg, bg, seq=None, tag='span', cls=None):
        """Opens a tag.

        This tracks how many tags are opened so they can all be closed at once
        if needed.
        """
        classes = []
        if cls:
            classes.append(cls)

        if 7 in self.esc_style:
            fg, bg = bg, fg

        k = self.update_css('f', fg)
        if k:
            classes.append(k)
        k = self.update_css('b', bg)
        if k:
            classes.append(k)

        classes.extend(self._style_classes(self.esc_style))
        if (not fg or fg < 16 or fg == 39) and 1 in self.esc_style and 'sb' in classes:
            classes.remove('sb')

        self.opened += 1
        attrs = []
        if classes:
            attrs.append('class="{0}"'.format(' '.join(classes)))
        if seq:
            attrs.append('data-seq="{0}"'.format(seq))
        html = '<{tag} {attrs}>'.format(tag=tag, attrs=' '.join(attrs))
        self.chunks.append(html)

    def close(self, tag='span', closeall=False):
        """Closes a tag."""
        if self.opened > 0:
            if closeall:
                self.chunks.extend(['</{}>'.format(tag)] * self.opened)
                self.opened = 0
            else:
                self.opened -= 1
                self.chunks.append('</{}>'.format(tag))

    def _escape_text(self, s):
        """Escape text

        In addition to escaping text, unicode characters are replaced with a
        span that will display the glyph using CSS.  This is to ensure that the
        text has a consistent width.
        """
        s = escape(s)
        s = re.sub(r'([\u0080-\uffff])',
                   lambda x: '<span class="u" data-glyph="&#x{:x};"> </span>'
                   .format(ord(x.group(1))), s)
        return s

    def _wrap_line(self, line, length, maxlength):
        """Wrap a line.

        A line is wrapped until it is short enough to fit within the pane.
        """
        line_c = 0
        while length and length > maxlength:
            cut = maxlength - length
            self.chunks.append(self._escape_text(line[:cut]))
            self.chunks.append('\n')
            line = line[cut:]
            length = len(line)
            line_c += 1
        return line_c, length, line

    def _render(self, s, size):
        """Render the content.

        Lines are wrapped and padded as needed.
        """
        cur_fg = None
        cur_bg = None
        self.esc_style = []
        self.chunks.append('<pre>')

        line_c = 0  # Number of lines created
        lines = s.split('\n')
        for line_i, line in enumerate(lines):
            last_i = 0
            line_l = 0
            for m in re.finditer(r'\x1b\[([^m]*)m', line):
                start, end = m.span()
                c = line[last_i:start]

                if c and last_i == 0 and not self.opened:
                    self.open(cur_fg, cur_bg)

                c_len = len(c)
                line_l += c_len
                nl, line_l, c = self._wrap_line(c, line_l, size[0])
                line_c += nl

                self.chunks.append(self._escape_text(c))

                if last_i == 0:
                    self.close()

                last_i = end

                cur_fg, cur_bg = \
                    color.parse_escape(m.group(1), fg=cur_fg, bg=cur_bg,
                                       style=self.esc_style)

                self.close()
                self.open(cur_fg, cur_bg, m.group(1))

            c = line[last_i:]
            c_len = len(c)
            line_l += c_len

            pad = ''
            if c or c_len != size[0]:
                if not self.opened:
                    self.open(cur_fg, cur_bg)
                nl, line_l, c = self._wrap_line(c, line_l, size[0])
                if line_c + nl < size[1]:
                    line_c += nl
                    pad = ' ' * (size[0] - line_l)

            self.chunks.append(self._escape_text(c))
            self.close(closeall=True)

            if pad:
                self.open(None, None, cls='ns')
                self.chunks.append(pad)
                self.close()

            if c or line_i < len(lines) - 1:
                self.chunks.append('\n')
                line_c += 1

        if line_c < size[1]:
            self.open(None, None, cls='ns')
            while line_c < size[1]:
                self.chunks.append(' ' * size[0])
                self.chunks.append('\n')
                line_c += 1
            self.close(closeall=True)

        self.chunks.append('</pre>')

    def _add_separator(self, vertical, size):
        """Add a separator."""
        if vertical:
            cls = 'v'
            rep = '<span class="u ns" data-glyph="&#x2500"> </span>'
        else:
            cls = 'h'
            rep = '<span class="u ns" data-glyph="&#x2502"> </span>\n'

        self.chunks.append('<div class="{} sep"><pre>'.format(cls))
        self.open(None, None)
        self.chunks.append(rep * size)
        self.close()
        self.chunks.append('</pre></div>')

    def _render_pane(self, pane):
        """Recursively render a pane as HTML.

        Panes without sub-panes are grouped.  Panes with sub-panes are grouped
        by their orientation.
        """
        if pane.panes:
            if pane.vertical:
                self.chunks.append('<div class="v">')
            else:
                self.chunks.append('<div class="h">')
            for i, p in enumerate(pane.panes):
                if p.x != 0 and p.x > pane.x:
                    self._add_separator(False, p.size[1])
                if p.y != 0 and p.y > pane.y:
                    self._add_separator(True, p.size[0])
                self._render_pane(p)

            self.chunks.append('</div>')
        else:
            self.chunks.append('<div id="p{}" class="pane" data-size="{}">'
                               .format(pane.identifier, ','.join(map(str, pane.size))))
            self._render(utils.get_contents('%{}'.format(pane.identifier)),
                         pane.size)
            self.chunks.append('</div>')

    def render_pane(self, pane):
        """Render a pane as HTML."""
        self.opened = 0
        self.chunks = []
        self.win_size = pane.size
        self.reset_css()
        self._render_pane(pane)
        return tpl.substitute(panes=''.join(self.chunks),
                              css=self.render_css(), prefix=classname)


def main():
    parser = argparse.ArgumentParser(description='Render tmux panes as HTML')
    parser.add_argument('target', default='', help='Target window or pane')
    parser.add_argument('--light', action='store_true', help='Light background')
    args = parser.parse_args()

    window = args.target
    pane = None
    session = None
    if window.find(':') != -1:
        session, window = window.split(':', 1)

    if window.find('.') != -1:
        window, pane = window.split('.', 1)
        window = int(window)
        pane = int(pane)
    else:
        window = int(window)

    root = utils.get_layout(window, session)
    target_pane = root
    if isinstance(pane, int):
        panes = utils.pane_list(root)
        target_pane = panes[pane]

    # Dark backgrounds are very common for terminal emulators and porn sites.
    # The use of dark backgrounds for anything else just looks weird.  I was
    # able to scientifically prove this through the use of the finest
    # recreational drugs and special goggles I made out of toilet paper rolls.
    fg = (0xfa, 0xfa, 0xfa)
    bg = (0, 0, 0)

    if args.light:
        fg, bg = bg, fg

    r = Renderer(fg, bg)
    with open('test2.html', 'wb') as fp:
        fp.write(r.render_pane(target_pane).encode('utf8'))
        # fp.write(r.render(term_content, term_size))
