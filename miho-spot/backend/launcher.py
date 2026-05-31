"""
Miho-spot Backend Launcher
Run with: python launcher.py --server
or:       python launcher.py --gui
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Miho-spot Backend")
    parser.add_argument("--server", action="store_true", help="Start FastAPI server")
    parser.add_argument("--gui", action="store_true", help="Start PyQt6 desktop GUI")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="API server host")

    args = parser.parse_args()

    if args.gui:
        from app.gui.main_window import run_gui
        run_gui()
    elif args.server:
        from main import run_server
        run_server(host=args.host, port=args.port)
    else:
        # Default: start both
        import threading
        print("[Miho-spot] Starting Miho-spot Backend...")
        print("[Miho-spot] API Server: http://localhost:8000")
        print("[Miho-spot] API Docs: http://localhost:8000/docs")

        # Start API server in background
        server_thread = threading.Thread(
            target=lambda: __import__("main").run_server(host=args.host, port=args.port),
            daemon=True,
        )
        server_thread.start()

        try:
            from app.gui.main_window import run_gui
            run_gui()
        except ImportError:
            print("[Miho-spot] PyQt6 not available, running server only.")
            server_thread.join()


if __name__ == "__main__":
    main()
