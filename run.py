"""Scout CLI.

Usage:
  python run.py once    # full cycle: scan -> triage -> score -> brief -> drafts
  python run.py scan     # hunt + triage + score only
  python run.py brief    # regenerate the daily brief
  python run.py serve    # dashboard on http://localhost:<SCOUT_PORT>
  python run.py watch    # ALWAYS-ON: full cycle every --interval hours
"""
import argparse

from scout import config, memory, skills


def main():
    ap = argparse.ArgumentParser(description="Scout — the always-on funding agent")
    ap.add_argument("cmd", choices=["once", "scan", "brief", "serve", "watch"],
                    help="once = full cycle; serve = dashboard; watch = always-on")
    ap.add_argument("--interval", type=float, default=6.0,
                    help="watch mode: hours between cycles (default 6)")
    ap.add_argument("--no-drafts", action="store_true",
                    help="watch mode: skip ultra-tier drafting")
    args = ap.parse_args()

    memory.init()
    skills.install_builtins()

    if args.cmd == "serve":
        import uvicorn
        from scout.server import app
        uvicorn.run(app, host="0.0.0.0", port=config.SCOUT_PORT)
        return

    if args.cmd == "watch":
        import time
        from scout import pipeline
        print(f"[watch] always-on: one cycle every {args.interval}h — Ctrl+C to stop")
        while True:
            started = time.time()
            try:
                result = pipeline.run_cycle(drafts=not args.no_drafts)
                print(f"[watch] cycle done: {result['new']} new, "
                      f"{result['triaged']} scored")
            except Exception as e:  # one bad cycle must never kill the agent
                print(f"[watch] cycle failed (continuing): {e}")
            sleep_for = max(60.0, args.interval * 3600 - (time.time() - started))
            time.sleep(sleep_for)

    from scout import pipeline

    if args.cmd == "once":
        result = pipeline.run_cycle()
        print("\n" + "=" * 60 + "\nBRIEF\n" + "=" * 60 + "\n")
        print(result["brief"])
    elif args.cmd == "scan":
        new = pipeline.scan()
        kept = 0
        for opp_id in new:
            if pipeline.triage(opp_id):
                pipeline.score(opp_id)
                kept += 1
        print(f"[scan] {len(new)} new, {kept} live opportunities")
    elif args.cmd == "brief":
        print(pipeline.brief())


if __name__ == "__main__":
    main()
