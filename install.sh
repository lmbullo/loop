#!/bin/sh
# loop-install/1: install a `loop` launcher for the current user or all users.
set -eu

NAME=loop
MARKER='# loop-install/1'
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON=${PYTHON:-python3}
PREFIX=${PREFIX:-}
BINDIR=${BINDIR:-}
SYSTEM=0
FORCE=0
DRY=0
ACTION=install

die() {
    printf 'install: %s\n' "$*" >&2
    exit 2
}

usage() {
    cat <<EOF
usage: ./install.sh [options]

Install a $NAME launcher for $ROOT/run.py.

options:
  --prefix DIR   installation prefix (default: \$HOME/.local)
  --bindir DIR   directory for the launcher (default: PREFIX/bin)
  --system       install for all users (default prefix: /usr/local)
  --uninstall    remove the launcher
  --force        replace or remove a file this installer did not create
  --dry-run      print actions without writing
  -h, --help     show this help

environment:
  PREFIX         default prefix
  BINDIR         default launcher directory
  PYTHON         interpreter baked into the launcher (default: python3)

examples:
  ./install.sh
  sudo ./install.sh --system
  ./install.sh --prefix "\$HOME/.local"
  ./install.sh --uninstall
EOF
}

while [ $# -gt 0 ]; do
    case $1 in
        --prefix)
            [ $# -ge 2 ] || die "--prefix needs a value"
            PREFIX=$2
            shift 2
            ;;
        --prefix=*)
            PREFIX=${1#*=}
            shift
            ;;
        --bindir)
            [ $# -ge 2 ] || die "--bindir needs a value"
            BINDIR=$2
            shift 2
            ;;
        --bindir=*)
            BINDIR=${1#*=}
            shift
            ;;
        --system)
            SYSTEM=1
            shift
            ;;
        --uninstall)
            ACTION=uninstall
            shift
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --dry-run)
            DRY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            [ $# -eq 0 ] || die "unexpected argument: $1"
            ;;
        *)
            die "unknown option: $1 (try --help)"
            ;;
    esac
done

if [ -z "$BINDIR" ]; then
    if [ -z "$PREFIX" ]; then
        if [ "$SYSTEM" -eq 1 ]; then
            PREFIX=/usr/local
        else
            [ -n "${HOME:-}" ] || die "HOME is unset; pass --prefix or --bindir"
            PREFIX=$HOME/.local
        fi
    fi
    BINDIR=$PREFIX/bin
fi
DEST=$BINDIR/$NAME

[ -f "$ROOT/run.py" ] || die "run.py not found next to install.sh: $ROOT"
[ -f "$ROOT/manifest.json" ] || die "manifest.json not found next to install.sh: $ROOT"

is_ours() {
    [ -f "$1" ] && grep -F "$MARKER" "$1" >/dev/null 2>&1
}

if [ "$ACTION" = uninstall ]; then
    if [ ! -e "$DEST" ] && [ ! -L "$DEST" ]; then
        printf 'not installed: %s\n' "$DEST"
        exit 0
    fi
    if ! is_ours "$DEST" && [ "$FORCE" -ne 1 ]; then
        die "refusing to remove foreign file: $DEST (use --force)"
    fi
    if [ "$DRY" -eq 1 ]; then
        printf 'would remove %s\n' "$DEST"
        exit 0
    fi
    rm -f "$DEST"
    printf 'removed %s\n' "$DEST"
    exit 0
fi

command -v "$PYTHON" >/dev/null 2>&1 || die "python interpreter not found: $PYTHON (set PYTHON=...)"
if { [ -e "$DEST" ] || [ -L "$DEST" ]; } && ! is_ours "$DEST" && [ "$FORCE" -ne 1 ]; then
    die "refusing to overwrite foreign file: $DEST (use --force)"
fi

if [ "$DRY" -eq 1 ]; then
    printf 'would install %s -> %s/run.py\n' "$DEST" "$ROOT"
    exit 0
fi

mkdir -p "$BINDIR" || die "cannot create $BINDIR"
[ -w "$BINDIR" ] || die "no write access: $BINDIR (use --system with sudo or --prefix)"

quote() {
    printf "'"
    printf '%s' "$1" | sed "s/'/'\\\\''/g"
    printf "'"
}

tmp=$BINDIR/.$NAME.$$
trap 'rm -f "$tmp"' 0 1 2 15
{
    printf '#!/bin/sh\n'
    printf '%s root=%s\n' "$MARKER" "$ROOT"
    printf 'exec %s %s "$@"\n' "$(quote "$PYTHON")" "$(quote "$ROOT/run.py")"
} >"$tmp"
chmod 755 "$tmp"
mv -f "$tmp" "$DEST"
trap - 0 1 2 15

printf 'installed %s -> %s/run.py\n' "$DEST" "$ROOT"
case ":${PATH:-}:" in
    *":$BINDIR:"*)
        printf 'run: %s --json\n' "$NAME"
        ;;
    *)
        printf 'PATH: add %s to PATH, e.g.\n  export PATH="%s:$PATH"\n' "$BINDIR" "$BINDIR"
        ;;
esac
