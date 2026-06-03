# SCOP: Like I'm Ten

## What is the virtual page model?

Imagine the consumer (the thing reading the stream) has a whiteboard for each room.

When a stream arrives with `intent: "query"`, the consumer **erases the whiteboard and draws a fresh picture**. When `intent: "action"`, it only updates the corner of the board where the progress spinner lives — the rest stays.

Every named thing on the board is called a **slot**. A slot has an `id`. You write to a slot by sending events with that `id`. Slots are typed:

| Slot type | How you open it | How you close it |
| --------- | --------------- | ---------------- |
| Scalar    | `SCALAR_SET`    | `SCALAR_CLEAR`   |
| List      | `LIST_DECLARE`  | `LIST_END`       |
| Table     | `TABLE_DECLARE` | `TABLE_END`      |
| Process   | `PROCESS_BEGIN` | `PROCESS_END`    |

---

## What the whiteboard looks like (concrete example)

Say we run `ourapp snapshot`. The producer emits this stream:

```jsonc
{"msgid": "PAGE_BEGIN",      "room": "snapshot", "title": "Snapshots", "intent": "query", ...}
{"msgid": "SCALAR_SET",      "room": "snapshot", "id": "tracked", "label": "Tracked files", "value": 1042, "type": "number", ...}
{"msgid": "LIST_DECLARE",    "room": "snapshot", "id": "changes",  "label": "Changed files", "ordered": false, ...}
{"msgid": "LIST_APPEND",     "room": "snapshot", "id": "changes",  "item_id": "f1", "value": "docs/intro.md", ...}
{"msgid": "LIST_APPEND",     "room": "snapshot", "id": "changes",  "item_id": "f2", "value": "docs/api.md", ...}
{"msgid": "LIST_END",        "room": "snapshot", "id": "changes",  ...}
{"msgid": "TABLE_DECLARE",   "room": "snapshot", "id": "snaps",   "label": "Snapshots", "schema": ["name","files","date"], ...}
{"msgid": "TABLE_ROW",       "room": "snapshot", "id": "snaps",   "row_id": "s1", "values": {"name":"snap-001","files":42,"date":"2026-05-30"}, ...}
{"msgid": "TABLE_END",       "room": "snapshot", "id": "snaps",   ...}
{"msgid": "PAGE_END",        "room": "snapshot", ...}
```

After `PAGE_END`, the consumer's in-memory model for the `"snapshot"` room looks like this:

```proto
room: "snapshot"
title: "Snapshots"
slots:
  tracked        (scalar)
    label:  "Tracked files"
    value:  1042
    type:   number

  changes        (list, unordered)
    label:  "Changed files"
    items:
      f1 → "docs/intro.md"
      f2 → "docs/api.md"

  snaps          (table)
    label:  "Snapshots"
    schema: [name, files, date]
    rows:
      s1 → {name: "snap-001", files: 42, date: "2026-05-30"}
```

The consumer knows nothing about what `ourapp` does. It just reads the stream, fills in the slots, and renders whatever it finds.

---

## How a consumer discovers what to render

A consumer needs no app-specific code and no separate manifest file. It uses the producer's own flags as a live discovery API.

**Step 1 — find the rooms (tabs)**

```
ourapp --help
```

The `LIST_APPEND` items where `kind: "group"` are subrooms — each becomes a tab or nav entry. Items where `kind: "action"` are commands available in the current room.

**Step 2 — recurse into each room**

For each subroom, repeat `--help` on that path:

```
ourapp snapshot --help   → "snapshot" room: its commands and params
ourapp snapshot --status → "snapshot" room: its current scalar data
ourapp snapshot --list   → "snapshot" room: its content (table or list)
```

After these three calls per room the consumer has everything: navigation structure, input form definitions (from `params`), stat cards, and content — with zero app knowledge.

**Step 3 — render in real time**

Rooms don't need to be fully probed before rendering starts. A consumer MAY:

- Render each room's page as its probe stream completes (`PAGE_END` received)
- Display a loading placeholder for rooms still being probed
- Lazy-probe rooms only when the user navigates to them

This means a GUI can be **fully live and app-agnostic** — it wires up as fast as the producer responds, with no manifest file to ship or keep in sync.

**The `kind: "group"` chain is the tree**

```
null (root)
  └─ snapshot          ← kind: "group" in root --help
       └─ diff         ← kind: "group" in snapshot --help
```

Follow `kind: "group"` links recursively and you have the full room tree.

---

## Key things to remember

- **One whiteboard per room.** `"snapshot"` and `"snapshot/diff"` are different boards.
- **`PAGE_BEGIN`/`PAGE_END` wrap the stream, not the page lifetime.** The board keeps existing between runs; `intent: "query"` is what tells the consumer to repaint it.
- **Slots are addressed by `id`.** Two `SCALAR_SET` events with the same `id` — the second one replaces the first.
- **The consumer needs zero app knowledge.** It just follows the events.
