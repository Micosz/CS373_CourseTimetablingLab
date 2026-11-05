using System;
using System.Collections.Generic;
using System.Linq;
using Godot;

namespace RoomMap;

/// <summary>
/// The room map: schedulable rooms are rows and the time of one day is columns. When the week changes, each session
/// glides from last week's room row to this week's, so room changes (and Labs freed in non-Lab weeks) are visible.
/// </summary>
public partial class RoomMapView : Control
{
    public event Action<Block?>? HoverChanged;
    public event Action<Block>? BlockClicked;

    public Schedule? Schedule { get; private set; }
    public int Week { get; private set; } = 1;
    public int Day { get; private set; }
    public string? SelectedSession { get; set; }
    public bool Compact { get; set; }

    const float LabelWidth = 132, HeaderHeight = 26, AnimSeconds = 0.45f;
    readonly Dictionary<string, Rect2> previous = [];
    float anim = 1;
    Block? hover;
    readonly Dictionary<BlockState, StyleBoxFlat> styles = [];
    StyleBoxFlat selectedStyle = null!, selectedGlow = null!, hoverStyle = null!, unassignedStyle = null!;

    public override void _Ready()
    {
        MouseFilter = MouseFilterEnum.Stop;
        TooltipText = " ";
        ClipContents = true;
        foreach (BlockState s in Enum.GetValues<BlockState>())
        {
            var color = Palette.Of(s);
            var sb = Ui.Box(color, 7, s == BlockState.LabUnnecessary ? new Color(Palette.Coral, 0.55f) : null, s == BlockState.LabUnnecessary ? 5 : 0, 0);
            styles[s] = sb;
        }
        unassignedStyle = Ui.Box(Palette.Cream, 7, null, 0, 0, Palette.Coral, 2);
        // A glow is a shadow, which StyleBoxFlat fills under the whole box: draw it behind the block, the border on top.
        selectedGlow = Ui.Box(Palette.Gold, 9, new Color(Palette.Gold, 0.7f), 8, 0);
        selectedStyle = Ui.Box(new Color(0, 0, 0, 0), 8, null, 0, 0, Palette.Gold, 3);
        hoverStyle = Ui.Box(new Color(1, 1, 1, 0.18f), 8, null, 0, 0, Palette.Gold, 2);
        CustomMinimumSize = new Vector2(600, 300);
    }

    public void SetSchedule(Schedule? schedule, bool animate = false)
    {
        if (animate && Schedule is not null) Capture();
        Schedule = schedule;
        hover = null;
        if (animate) anim = 0; else previous.Clear();
        QueueRedraw();
    }

    public void SetWeekDay(int week, int day, bool animate = true)
    {
        if (week == Week && day == Day) return;
        // Gliding only makes sense within a day; a day switch redraws at once.
        if (animate && day == Day && Schedule is not null) { Capture(); anim = 0; }
        else { previous.Clear(); anim = 1; }
        Week = week;
        Day = day;
        hover = null;
        QueueRedraw();
    }

    void Capture()
    {
        previous.Clear();
        if (Schedule is null) return;
        var lanes = UnassignedLanes(Schedule.Blocks(Week, Day));
        foreach (var b in Schedule.Blocks(Week, Day))
            if (b.SessionId is not null) previous[b.SessionId] = RectOf(b, lanes);
    }

    public override void _Process(double delta)
    {
        if (anim >= 1) return;
        anim = Math.Min(1, anim + (float)delta / AnimSeconds);
        QueueRedraw();
    }

    // ---- geometry ----------------------------------------------------------------------------------------------

    int RowCount => (Schedule?.Index.Rooms.Length ?? 0) + 1; // + unassigned row

    float RowHeight => Math.Max(14, (Size.Y - HeaderHeight - 4) / Math.Max(1, RowCount + 0.25f));

    float GridLeft => Compact ? 96 : LabelWidth;

    float XOf(int minute)
    {
        var idx = Schedule!.Index;
        return GridLeft + (minute - idx.DayStart) / (float)(idx.DayEnd - idx.DayStart) * (Size.X - GridLeft - 8);
    }

    float RowTop(int row) => HeaderHeight + row * RowHeight + (row >= Schedule!.Index.Rooms.Length ? RowHeight * 0.25f : 0);

    int RowOf(string? roomId)
    {
        if (roomId is null) return Schedule!.Index.Rooms.Length;
        var rooms = Schedule!.Index.Rooms;
        for (var i = 0; i < rooms.Length; i++) if (rooms[i].Id == roomId) return i;
        return rooms.Length;
    }

    Rect2 RectOf(Block b, Dictionary<Block, (int Lane, int Lanes)> lanes)
    {
        var row = RowOf(b.RoomId);
        float x0 = XOf(b.Start), x1 = XOf(b.End), top = RowTop(row) + 3, h = RowHeight - 6;
        if (b.State == BlockState.Unassigned && lanes.TryGetValue(b, out var lane))
        {
            var lh = h / lane.Lanes;
            top += lane.Lane * lh;
            h = lh - 1;
        }
        if (b.State is BlockState.Unavailable or BlockState.External) { top = RowTop(row) + 1; h = RowHeight - 2; }
        return new Rect2(x0 + 1, top, Math.Max(3, x1 - x0 - 2), Math.Max(2, h));
    }

    /// <summary>Stacks overlapping unassigned sessions into lanes of the bottom row.</summary>
    static Dictionary<Block, (int, int)> UnassignedLanes(List<Block> blocks)
    {
        var result = new Dictionary<Block, (int, int)>();
        var list = blocks.Where(b => b.State == BlockState.Unassigned).OrderBy(b => b.Start).ToList();
        var laneEnds = new List<int>();
        var assigned = new List<(Block, int)>();
        foreach (var b in list)
        {
            var lane = laneEnds.FindIndex(e => e <= b.Start);
            if (lane < 0) { lane = laneEnds.Count; laneEnds.Add(0); }
            laneEnds[lane] = b.End;
            assigned.Add((b, lane));
        }
        var lanes = Math.Max(1, Math.Min(4, laneEnds.Count));
        foreach (var (b, lane) in assigned) result[b] = (Math.Min(lane, lanes - 1), lanes);
        return result;
    }

    static float Ease(float t) => 1 - (float)Math.Pow(1 - t, 3);

    // ---- drawing -----------------------------------------------------------------------------------------------

    public override void _Draw()
    {
        var font = Ui.Regular;
        var bold = Ui.Bold;
        if (Schedule is null)
        {
            DrawString(font, new Vector2(20, 40), "กำลังโหลดข้อมูล… Loading", HorizontalAlignment.Left, -1, 16, Palette.InkSoft);
            return;
        }
        var idx = Schedule.Index;
        var rooms = idx.Rooms;
        var rh = RowHeight;
        var right = Size.X - 8;
        var labelSize = Compact ? 12 : 13;

        // Row bands and labels.
        for (var r = 0; r <= rooms.Length; r++)
        {
            var top = RowTop(r);
            var band = new Rect2(GridLeft, top, right - GridLeft, rh);
            if (r < rooms.Length)
            {
                var room = rooms[r];
                DrawRect(band, room.IsLab ? new Color(Palette.TealWash, 0.7f) : (r % 2 == 0 ? new Color(Palette.White, 0.75f) : new Color(Palette.White, 0.35f)));
                var name = room.IsLab ? room.Id.Replace("SIM-", "") : room.Id;
                DrawString(bold, new Vector2(8, top + rh / 2 + 5), name, HorizontalAlignment.Left, GridLeft - 10, labelSize, room.IsLab ? Palette.TealDark : Palette.Ink);
                if (!Compact)
                    DrawString(font, new Vector2(78, top + rh / 2 + 5), $"{(room.IsLab ? "Lab" : "Lec")} {room.Capacity}", HorizontalAlignment.Left, GridLeft - 80, 11, Palette.InkSoft);
            }
            else
            {
                DrawRect(band, new Color(Palette.CoralWash, 0.5f));
                DrawString(bold, new Vector2(8, top + rh / 2 + 5), Compact ? "ไม่ได้ห้อง" : "ไม่ได้ห้อง ·  none", HorizontalAlignment.Left, GridLeft - 10, labelSize, Palette.Coral);
            }
        }
        // Lab / lecture divider.
        if (idx.LabCount > 0)
        {
            var y = RowTop(idx.LabCount);
            DrawLine(new Vector2(4, y), new Vector2(right, y), new Color(Palette.Teal, 0.6f), 2);
        }

        // Hour grid.
        for (var m = idx.DayStart; m <= idx.DayEnd; m += 60)
        {
            var x = XOf(m);
            DrawLine(new Vector2(x, HeaderHeight - 4), new Vector2(x, RowTop(rooms.Length) + rh), Palette.Line, 1);
            if (!Compact || (m / 60) % 2 == 0)
                DrawString(font, new Vector2(x - 16, HeaderHeight - 9), Ui.Clock(m), HorizontalAlignment.Left, -1, 11, Palette.InkSoft);
        }

        // Background: unavailable windows and external bookings.
        foreach (var b in idx.Background(Week, Day))
        {
            var rect = RectOf(b, []);
            if (b.State == BlockState.Unavailable)
            {
                DrawRect(rect, Palette.StoneWash);
                // Diagonal hatching clipped to the rect: point(u) = (x + u, bottom - u), u in [0, height].
                var h = rect.Size.Y;
                for (var x = rect.Position.X - h; x < rect.End.X; x += 9)
                {
                    float u0 = Math.Max(0, rect.Position.X - x), u1 = Math.Min(h, rect.End.X - x);
                    if (u0 < u1)
                        DrawLine(new Vector2(x + u0, rect.End.Y - u0), new Vector2(x + u1, rect.End.Y - u1), new Color(Palette.Stone, 0.45f), 1);
                }
            }
            else
            {
                DrawStyleBox(styles[BlockState.External], rect);
                Label(rect, b.Label, Palette.White, 11);
            }
        }

        // Sessions.
        var blocks = Schedule.Blocks(Week, Day);
        var lanes = UnassignedLanes(blocks);
        var t = Ease(anim);
        Rect2? selectedRect = null;
        foreach (var b in blocks.OrderBy(b => b.State == BlockState.LabUnnecessary ? 1 : 0))
        {
            var target = RectOf(b, lanes);
            var rect = target;
            var alpha = 1f;
            if (anim < 1)
            {
                if (b.SessionId is not null && previous.TryGetValue(b.SessionId, out var from))
                    rect = new Rect2(from.Position.Lerp(target.Position, t), from.Size.Lerp(target.Size, t));
                else alpha = t;
            }
            var style = b.State == BlockState.Unassigned ? unassignedStyle : styles[b.State];
            if (alpha < 1)
            {
                var faded = (StyleBoxFlat)style.Duplicate();
                faded.BgColor = new Color(faded.BgColor, faded.BgColor.A * alpha);
                faded.ShadowColor = new Color(faded.ShadowColor, faded.ShadowColor.A * alpha);
                style = faded;
            }
            if (b.SessionId is not null && b.SessionId == SelectedSession) DrawStyleBox(selectedGlow, rect.Grow(2));
            DrawStyleBox(style, rect);
            var fg = b.State switch
            {
                BlockState.Unassigned => Palette.Coral,
                BlockState.Lecture => Palette.Ink,
                _ => Palette.White,
            };
            if (b.State != BlockState.Unassigned || rect.Size.Y >= 12)
                Label(rect, b.Label, new Color(fg, alpha), Compact ? 10 : 11);
            if (b.SessionId == SelectedSession) selectedRect = rect;
            if (hover is not null && ReferenceEquals(b, hover)) DrawStyleBox(hoverStyle, rect.Grow(1));
        }
        if (selectedRect is { } sel) DrawStyleBox(selectedStyle, sel.Grow(2));
    }

    void Label(Rect2 rect, string text, Color color, int size)
    {
        var font = Ui.Regular;
        if (rect.Size.X < 22 || rect.Size.Y < 10) return;
        var width = font.GetStringSize(text, HorizontalAlignment.Left, -1, size).X;
        var shown = text;
        if (width > rect.Size.X - 8)
        {
            shown = text.Length > 4 ? text[..Math.Max(1, (int)(text.Length * (rect.Size.X - 8) / width))] : text;
            if (font.GetStringSize(shown, HorizontalAlignment.Left, -1, size).X > rect.Size.X - 4) return;
        }
        DrawString(font, new Vector2(rect.Position.X + 4, rect.Position.Y + rect.Size.Y / 2 + size * 0.36f), shown,
            HorizontalAlignment.Left, rect.Size.X - 6, size, color);
    }

    // ---- interaction -------------------------------------------------------------------------------------------

    public Block? HitTest(Vector2 at)
    {
        if (Schedule is null) return null;
        var blocks = Schedule.Blocks(Week, Day);
        var lanes = UnassignedLanes(blocks);
        for (var i = blocks.Count - 1; i >= 0; i--)
            if (RectOf(blocks[i], lanes).HasPoint(at)) return blocks[i];
        foreach (var b in Schedule.Index.Background(Week, Day).Where(b => b.State == BlockState.External))
            if (RectOf(b, []).HasPoint(at)) return b;
        return null;
    }

    public override void _GuiInput(InputEvent e)
    {
        if (e is InputEventMouseMotion motion)
        {
            var hit = HitTest(motion.Position);
            if (!ReferenceEquals(hit, hover)) { hover = hit; HoverChanged?.Invoke(hit); QueueRedraw(); }
        }
        else if (e is InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } click && HitTest(click.Position) is { } b)
        {
            if (b.SessionId is not null) SelectedSession = b.SessionId;
            BlockClicked?.Invoke(b);
            QueueRedraw();
        }
    }

    public override void _Notification(int what)
    {
        if (what == NotificationMouseExit && hover is not null) { hover = null; HoverChanged?.Invoke(null); QueueRedraw(); }
        if (what == NotificationResized) QueueRedraw();
    }

    public override string _GetTooltip(Vector2 atPosition) => HitTest(atPosition) is { } b && Schedule is not null ? Describe(Schedule, b) : "";

    public static string Describe(Schedule s, Block b)
    {
        if (b.State == BlockState.External)
            return $"จองภายนอก external booking {b.ClassId}\nห้อง room {b.RoomId} · {Ui.Day(b.Day)} {Ui.Clock(b.Start)}–{Ui.Clock(b.End)} · สัปดาห์ week {b.Week}";
        var session = b.SessionId is not null ? s.Index.Sessions.GetValueOrDefault(b.SessionId) : null;
        var labWeeks = session is null ? "" : string.Join(",", session.LabWeeks.OrderBy(w => w));
        var room = b.RoomId is null ? "— (ไม่ได้ห้อง unassigned)" : $"{b.RoomId} ({(s.Index.RoomById[b.RoomId].IsLab ? "Lab" : "lecture")}, {s.Index.RoomById[b.RoomId].Capacity} ที่นั่ง)";
        return $"วิชา class {b.ClassId}  ·  offering {b.CourseId}\n" +
               $"session {b.SessionId}  ·  สัปดาห์ week {b.Week}\n" +
               $"ห้อง room {room}\n" +
               $"{Ui.Day(b.Day)} {Ui.Clock(b.Start)}–{Ui.Clock(b.End)}  ·  สัปดาห์ที่ต้องใช้ Lab: {(labWeeks == "" ? "ไม่มี none" : labWeeks)}\n" +
               Palette.Name(b.State);
    }
}
