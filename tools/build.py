"""Build the LoxBerry installation ZIP with LF text and Unix executable modes."""
import argparse
import configparser
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"bin", "config", "dpkg", "uninstall", "webfrontend", "icons"}
FILES = {"plugin.cfg", "preroot.sh", "preupgrade.sh", "postinstall.sh", "postupgrade.sh", "postroot.sh", "README.md", "LICENSE"}


def validate_metadata(cfg):
    # Mandatory fields checked by LoxBerry sbin/plugininstall.pl before any hooks.
    required = {"AUTHOR": ("NAME", "EMAIL"),
                "PLUGIN": ("VERSION", "NAME", "TITLE", "FOLDER"),
                "SYSTEM": ("INTERFACE",)}
    for section, keys in required.items():
        for key in keys:
            if cfg.get(section, key, fallback="").strip() in {"", "0"}:
                raise ValueError(f"Missing mandatory LoxBerry metadata: {section}.{key}")
    if cfg["SYSTEM"]["INTERFACE"] not in {"1.0", "2.0"}:
        raise ValueError("Unsupported LoxBerry plugin interface")


def build(output, legacy_identity=False):
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "plugin.cfg")
    validate_metadata(cfg)
    version = cfg["PLUGIN"]["VERSION"]
    output.mkdir(parents=True, exist_ok=True)
    suffix = "-legacy-upgrade" if legacy_identity else ""
    target = output / f"loxberry-samsung-local-{version}{suffix}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(ROOT.rglob("*")):
            relative = file.relative_to(ROOT)
            if not file.is_file() or "__pycache__" in relative.parts:
                continue
            if relative.parts[0] not in DIRECTORIES and relative.as_posix() not in FILES:
                continue
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 10, 3, 0, 0, 0))
            info.create_system = 3
            executable = file.suffix in {".sh", ".pl"}
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            payload = file.read_bytes()
            if relative.as_posix() == "plugin.cfg" and legacy_identity:
                # Pre-GitHub builds used this identity. LoxBerry hashes author
                # name/email + plugin name/folder to select the upgrade path.
                import io
                cfg["AUTHOR"]["NAME"] = "Samsung Local Contributors"
                cfg["AUTHOR"]["EMAIL"] = "samsung-local@localhost.invalid"
                stream = io.StringIO()
                cfg.write(stream)
                payload = stream.getvalue().encode("utf-8")
            if file.suffix != ".png":
                payload = payload.replace(b"\r\n", b"\n")
            archive.writestr(info, payload)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    print(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--legacy-identity", action="store_true",
                        help="Preserve the identity of pre-GitHub test installations")
    args = parser.parse_args()
    build(args.output, args.legacy_identity)
