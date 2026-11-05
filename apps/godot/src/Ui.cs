using System;
using Godot;

namespace RoomMap;

public static class Palette
{
    public static readonly Color Teal = Color.FromHtml("#2BA8A2");
    public static readonly Color TealDark = Color.FromHtml("#1E8C86");
    public static readonly Color Gold = Color.FromHtml("#FFD23F");
    public static readonly Color Coral = Color.FromHtml("#EF6C4A");
    public static readonly Color Sky = Color.FromHtml("#5DADE2");
    public static readonly Color Cream = Color.FromHtml("#FFF8E7");
    public static readonly Color Background = Color.FromHtml("#EFF8F7");

    // Neutrals derived for text, grid lines and background bookings.
    public static readonly Color Ink = Color.FromHtml("#20403E");
    public static readonly Color InkSoft = Color.FromHtml("#5F7A77");
    public static readonly Color Line = Color.FromHtml("#DCEBE9");
    public static readonly Color TealWash = Color.FromHtml("#DDF2F0");
    public static readonly Color SkyWash = Color.FromHtml("#E3F1FA");
    public static readonly Color CoralWash = Color.FromHtml("#FCE3DB");
    public static readonly Color Stone = Color.FromHtml("#B9B2A3");
    public static readonly Color StoneWash = Color.FromHtml("#ECE7DC");
    public static readonly Color White = Color.FromHtml("#FFFFFF");

    public static Color Of(BlockState state) => state switch
    {
        BlockState.LabNeeded => Teal,
        BlockState.LabUnnecessary => Coral,
        BlockState.Lecture => Sky,
        BlockState.External => Stone,
        BlockState.Unavailable => StoneWash,
        _ => Cream,
    };

    public static string Name(BlockState state) => state switch
    {
        BlockState.LabNeeded => "Lab · ต้องใช้ Lab สัปดาห์นี้",
        BlockState.LabUnnecessary => "Lab · ไม่จำเป็น (unnecessary)",
        BlockState.Lecture => "ห้องบรรยาย · lecture room",
        BlockState.External => "จองภายนอก · external booking",
        BlockState.Unavailable => "ห้องไม่ว่าง · unavailable",
        _ => "ไม่ได้ห้อง · unassigned",
    };
}

/// <summary>Theme and widget factories: pill buttons, 16px cream cards and soft coloured glows.</summary>
public static class Ui
{
    public static Font Regular { get; private set; } = null!;
    public static Font Bold { get; private set; } = null!;

    static readonly string[] FontNames = ["Leelawadee UI", "Noto Sans Thai UI", "Noto Sans Thai", "Sarabun", "Tahoma", "Segoe UI", "sans-serif"];

    public static StyleBoxFlat Box(Color bg, int radius = 16, Color? glow = null, int glowSize = 0, float margin = 14,
                                   Color? border = null, int borderWidth = 0)
    {
        var sb = new StyleBoxFlat { BgColor = bg, AntiAliasing = true };
        sb.SetCornerRadiusAll(radius);
        sb.SetContentMarginAll(margin);
        if (glow is { } g && glowSize > 0) { sb.ShadowColor = g; sb.ShadowSize = glowSize; sb.ShadowOffset = Vector2.Zero; }
        if (border is { } b && borderWidth > 0) { sb.BorderColor = b; sb.SetBorderWidthAll(borderWidth); }
        return sb;
    }

    static StyleBoxFlat PillBox(Color bg, Color? border = null, Color? glow = null)
    {
        var sb = Box(bg, 999, glow, glow is null ? 0 : 6, 0, border, border is null ? 0 : 2);
        sb.ContentMarginLeft = sb.ContentMarginRight = 16;
        sb.ContentMarginTop = sb.ContentMarginBottom = 7;
        return sb;
    }

    static void ButtonStyles(Theme t, string type, Color bg, Color fg, Color hover, Color pressed, Color pressedFg, Color? border)
    {
        t.SetStylebox("normal", type, PillBox(bg, border));
        t.SetStylebox("hover", type, PillBox(hover, border, new Color(Palette.Teal, 0.25f)));
        t.SetStylebox("pressed", type, PillBox(pressed, null, new Color(Palette.Teal, 0.35f)));
        t.SetStylebox("hover_pressed", type, PillBox(pressed, null, new Color(Palette.Gold, 0.55f)));
        t.SetStylebox("disabled", type, PillBox(new Color(bg, 0.45f), border is { } b ? new Color(b, 0.4f) : null));
        t.SetStylebox("focus", type, new StyleBoxEmpty());
        t.SetColor("font_color", type, fg);
        t.SetColor("font_hover_color", type, fg);
        t.SetColor("font_focus_color", type, fg);
        t.SetColor("font_pressed_color", type, pressedFg);
        t.SetColor("font_hover_pressed_color", type, pressedFg);
        t.SetColor("font_disabled_color", type, new Color(fg, 0.45f));
    }

    public static Theme BuildTheme()
    {
        Regular = new SystemFont { FontNames = FontNames, FontWeight = 400, Antialiasing = TextServer.FontAntialiasing.Gray };
        Bold = new SystemFont { FontNames = FontNames, FontWeight = 700, Antialiasing = TextServer.FontAntialiasing.Gray };
        var t = new Theme { DefaultFont = Regular, DefaultFontSize = 15 };

        ButtonStyles(t, "Button", Palette.White, Palette.TealDark, Palette.TealWash, Palette.Teal, Palette.White, Palette.Teal);
        t.SetTypeVariation("PrimaryButton", "Button");
        ButtonStyles(t, "PrimaryButton", Palette.Teal, Palette.White, Palette.TealDark, Palette.TealDark, Palette.White, null);
        t.SetTypeVariation("DangerButton", "Button");
        ButtonStyles(t, "DangerButton", Palette.Coral, Palette.White, Palette.Coral.Darkened(0.1f), Palette.Coral.Darkened(0.2f), Palette.White, null);
        t.SetTypeVariation("ChipButton", "Button");
        ButtonStyles(t, "ChipButton", Palette.Cream, Palette.TealDark, Palette.TealWash, Palette.TealDark, Palette.Gold, Palette.Line);
        t.SetConstant("h_separation", "Button", 6);
        ButtonStyles(t, "OptionButton", Palette.White, Palette.TealDark, Palette.TealWash, Palette.TealWash, Palette.TealDark, Palette.Teal);
        t.SetConstant("arrow_margin", "OptionButton", 12);
        t.SetColor("font_color", "Label", Palette.Ink);

        t.SetStylebox("panel", "PanelContainer", Box(Palette.Cream, 16, new Color(Palette.Teal, 0.18f), 14, 16));
        t.SetTypeVariation("InnerCard", "PanelContainer");
        t.SetStylebox("panel", "InnerCard", Box(Palette.White, 16, null, 0, 12, Palette.Line, 1));
        t.SetTypeVariation("HeroCard", "PanelContainer");
        t.SetStylebox("panel", "HeroCard", Box(Palette.Teal, 16, new Color(Palette.Teal, 0.35f), 16, 16));

        var field = Box(Palette.White, 12, null, 0, 8, Palette.Line, 2);
        t.SetStylebox("normal", "LineEdit", field);
        t.SetStylebox("focus", "LineEdit", Box(Palette.White, 12, new Color(Palette.Gold, 0.5f), 4, 8, Palette.Teal, 2));
        t.SetColor("font_color", "LineEdit", Palette.Ink);
        t.SetColor("caret_color", "LineEdit", Palette.TealDark);
        t.SetColor("selection_color", "LineEdit", new Color(Palette.Gold, 0.6f));

        t.SetStylebox("panel", "PopupMenu", Box(Palette.Cream, 14, new Color(Palette.Teal, 0.25f), 10, 8));
        t.SetStylebox("hover", "PopupMenu", Box(Palette.TealWash, 10, null, 0, 4));
        t.SetColor("font_color", "PopupMenu", Palette.Ink);
        t.SetColor("font_hover_color", "PopupMenu", Palette.TealDark);
        t.SetStylebox("panel", "TooltipPanel", Box(Palette.Cream, 12, new Color(Palette.Teal, 0.35f), 8, 10, Palette.Teal, 1));
        t.SetColor("font_color", "TooltipLabel", Palette.Ink);

        t.SetStylebox("background", "ProgressBar", Box(Palette.TealWash, 999, null, 0, 0));
        t.SetStylebox("fill", "ProgressBar", Box(Palette.Teal, 999, new Color(Palette.Teal, 0.4f), 4, 0));
        t.SetColor("font_color", "ProgressBar", Palette.Ink);

        var track = Box(Palette.TealWash, 999, null, 0, 3);
        t.SetStylebox("slider", "HSlider", track);
        t.SetStylebox("grabber_area", "HSlider", Box(Palette.Teal, 999, null, 0, 3));
        t.SetStylebox("grabber_area_highlight", "HSlider", Box(Palette.TealDark, 999, new Color(Palette.Gold, 0.6f), 4, 3));

        t.SetStylebox("panel", "AcceptDialog", Box(Palette.Cream, 16, null, 0, 12));
        t.SetStylebox("v_scroll", "VScrollBar", Box(new Color(Palette.Teal, 0.06f), 999, null, 0, 2));
        t.SetStylebox("grabber", "VScrollBar", Box(new Color(Palette.Teal, 0.45f), 999, null, 0, 2));
        t.SetStylebox("grabber_highlight", "VScrollBar", Box(Palette.Teal, 999, null, 0, 2));
        t.SetStylebox("grabber_pressed", "VScrollBar", Box(Palette.TealDark, 999, null, 0, 2));
        return t;
    }

    public static Label Text(string text, int size = 15, Color? color = null, bool bold = false, bool wrap = false)
    {
        var l = new Label { Text = text };
        if (size != 15) l.AddThemeFontSizeOverride("font_size", size);
        if (color is { } c) l.AddThemeColorOverride("font_color", c);
        if (bold) l.AddThemeFontOverride("font", Bold);
        if (wrap) { l.AutowrapMode = TextServer.AutowrapMode.WordSmart; l.CustomMinimumSize = new Vector2(10, 0); }
        return l;
    }

    public static Button Button(string text, string variation = "", Action? onPressed = null)
    {
        var b = new Button { Text = text, ThemeTypeVariation = variation, FocusMode = Control.FocusModeEnum.None };
        if (onPressed is not null) b.Pressed += onPressed;
        return b;
    }

    public static PanelContainer Card(Control child, string variation = "")
    {
        var p = new PanelContainer { ThemeTypeVariation = variation };
        p.AddChild(child);
        return p;
    }

    public static VBoxContainer VBox(int separation = 10, params Control[] children)
    {
        var box = new VBoxContainer();
        box.AddThemeConstantOverride("separation", separation);
        foreach (var c in children) box.AddChild(c);
        return box;
    }

    public static HBoxContainer HBox(int separation = 10, params Control[] children)
    {
        var box = new HBoxContainer();
        box.AddThemeConstantOverride("separation", separation);
        foreach (var c in children) box.AddChild(c);
        return box;
    }

    public static T Expand<T>(T c, bool horizontal = true, bool vertical = false) where T : Control
    {
        if (horizontal) c.SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
        if (vertical) c.SizeFlagsVertical = Control.SizeFlags.ExpandFill;
        return c;
    }

    public static Control Spacer() => Expand(new Control());

    public static OptionButton Options(params string[] items)
    {
        var o = new OptionButton { FocusMode = Control.FocusModeEnum.None };
        foreach (var i in items) o.AddItem(i);
        return o;
    }

    public static string Day(int day) => day switch
    {
        0 => "จ. Mon", 1 => "อ. Tue", 2 => "พ. Wed", 3 => "พฤ. Thu", 4 => "ศ. Fri", 5 => "ส. Sat", _ => "อา. Sun",
    };

    public static string Clock(int minute) => $"{minute / 60:00}:{minute % 60:00}";

    public static string Hours(double hours) => hours.ToString(hours % 1 == 0 ? "#,0" : "#,0.0");

    public static string ModeName(string mode) => mode == "fixed" ? "fixed · ห้องเดิมทั้งเทอม" : "weekly · เปลี่ยนห้องรายสัปดาห์";

    public static string MethodName(string method) => method switch
    {
        "greedy" => "Greedy", "hc" => "Hill climbing", "sa" => "Simulated annealing", "ga" => "Genetic algorithm", _ => method,
    };
}
