"""Local GUI service; importing the CLI does not import optional server dependencies."""


def serve(project=None, port=0, no_browser=False, root=None, allow_dir=()):
    import secrets
    import socket
    import webbrowser
    from pathlib import Path

    import uvicorn

    from .app import create_app

    token = secrets.token_urlsafe(32)
    # Bind before announcing/opening the URL, so port=0 has no allocation race.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", port or 0))
    sock.listen(128)
    address = f"http://127.0.0.1:{sock.getsockname()[1]}"
    app = create_app(
        root=root or Path.cwd(), token=token, origin=address, project=project, allow_dir=allow_dir
    )
    url = f"{address}/#{token}"
    print(url, flush=True)
    if not no_browser:
        webbrowser.open(url)
    try:
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", access_log=False)).run(sockets=[sock])
    finally:
        sock.close()
