"""Mock WhatsApp Console (README.md 9.1).

A small FastAPI app that lets you play Placement Cell / coordinator / student and post
timestamped messages, so the reconciliation and rule engine can be exercised end-to-end
without touching a real WhatsApp group.

Run with:
    uvicorn ingestion.mock_whatsapp.console:app --reload --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from core.schemas import SenderRole
from ingestion.mock_whatsapp import store

app = FastAPI(title="Mock WhatsApp Console")


def _render_page() -> str:
    rows = "".join(
        f"<tr>"
        f"<td>{m.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>"
        f"<td>{m.sender_role.value}</td>"
        f"<td>{m.sender_id}</td>"
        f"<td>{'yes' if m.is_forwarded else 'no'}</td>"
        f"<td>{m.body}</td>"
        f"</tr>"
        for m in reversed(store.get_all())
    )

    return f"""
    <html>
    <head><title>Mock WhatsApp Console</title></head>
    <body style="font-family: sans-serif; max-width: 900px; margin: 2rem auto;">
      <h2>Mock WhatsApp Console</h2>
      <p>Post a message as Placement Cell, Coordinator, or Student. Each post is timestamped
         and tagged with the matching source type for the reconciliation engine.</p>

      <form action="/post" method="post" style="margin-bottom: 2rem;">
        <label>Sender role:
          <select name="sender_role">
            <option value="placement_cell">Placement Cell</option>
            <option value="coordinator">Coordinator</option>
            <option value="student">Student</option>
          </select>
        </label><br><br>

        <label>Sender id: <input type="text" name="sender_id" value="demo_sender" required></label><br><br>

        <label>Forwarded message?
          <input type="checkbox" name="is_forwarded" value="true">
        </label><br><br>

        <label>Message body:<br>
          <textarea name="body" rows="4" cols="60" required></textarea>
        </label><br><br>

        <button type="submit">Post message</button>
      </form>

      <h3>Message history (newest first)</h3>
      <table border="1" cellpadding="6" cellspacing="0">
        <tr><th>Timestamp</th><th>Role</th><th>Sender</th><th>Forwarded</th><th>Body</th></tr>
        {rows}
      </table>
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def view_console() -> str:
    return _render_page()


@app.post("/post")
def post_message(
    sender_role: str = Form(...),
    sender_id: str = Form(...),
    body: str = Form(...),
    is_forwarded: str | None = Form(None),
) -> RedirectResponse:
    store.add_message(
        sender_id=sender_id,
        sender_role=SenderRole(sender_role),
        body=body,
        is_forwarded=is_forwarded is not None,
    )
    return RedirectResponse(url="/", status_code=303)


@app.get("/messages")
def list_messages() -> list[dict]:
    """JSON view of the current message log — useful for the extraction stage to poll later."""
    return [m.model_dump(mode="json") for m in store.get_all()]
