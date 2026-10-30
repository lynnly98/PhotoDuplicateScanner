"""Single entry point for both the portable app and its scanner subprocess."""
import sys
if __name__ == '__main__':
    if '--scan-worker' in sys.argv:
        sys.argv.remove('--scan-worker')
        import scanner
        scanner.main()
    else:
        import desktop
        sys.exit(desktop.main())
