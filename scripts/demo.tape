# Records docs/demo.gif with made-up data:  vhs scripts/demo.tape
Output docs/demo.gif

Require toktop
Set Shell "bash"
Set FontSize 14
Set Width 1400
Set Height 820
Set Padding 12
Set Framerate 20
Set TypingSpeed 60ms
Set Theme { "background": "#0f1420", "foreground": "#e6e6e6", "cursor": "#f2cc8f", "black": "#0f1420", "brightBlack": "#5c6370", "red": "#e06c75", "brightRed": "#e06c75", "green": "#98c379", "brightGreen": "#98c379", "yellow": "#f2cc8f", "brightYellow": "#f2cc8f", "blue": "#61afef", "brightBlue": "#61afef", "magenta": "#c678dd", "brightMagenta": "#c678dd", "cyan": "#56b6c2", "brightCyan": "#56b6c2", "white": "#e6e6e6", "brightWhite": "#ffffff" }

Hide
Type "clear && toktop --demo --lang en" Enter
Sleep 3s
Show

# Home: cycle through periods
Sleep 2.5s
Type "p"  Sleep 1.5s
Type "p"  Sleep 1.5s
# toggle a couple of sources off and back on
Type "c"  Sleep 1.2s
Type "o"  Sleep 1.2s
Type "t"  Sleep 1.5s

# Calendar: go back a couple of months
Type "2"  Sleep 2s
Left      Sleep 1.2s
Left      Sleep 1.5s

# Models
Type "3"  Sleep 2.5s

# Sessions + search
Type "4"  Sleep 1.5s
Type "/"  Sleep 0.5s
Type "refactor"  Sleep 2s
Escape    Sleep 1s

# Prices simulation
Type "5"  Sleep 3.5s
Type "p"  Sleep 2.5s

Type "1"  Sleep 1.5s
Hide
Type "q"
