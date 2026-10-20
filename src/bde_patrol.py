#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
"""
BDE Patrol Scanner
Autonomously scans for open-source and real-world spacecraft models/designs
from local directories, GitHub, and public technical repositories.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ShipScanResult:
    source: str  # "local", "github", "web"
    name: str
    path_or_url: str
    license: str
    copyright_status: str  # "open", "public_domain", "restricted"
    mass_kg: Optional[float] = None
    length_m: Optional[float] = None
    propulsion_type: Optional[str] = None
    isp_s: Optional[float] = None
    thrust_n: Optional[float] = None
    max_speed_m_s: Optional[float] = None
    crew: Optional[int] = None
    cargo_kg: Optional[float] = None
    atmo_capable: Optional[bool] = None
    notes: str = ""
    scan_timestamp: str = ""


class BDEPatrol:
    def __init__(self, base_dir: Path, cache_dir: Path):
        self.base_dir = base_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.scan_log: List[ShipScanResult] = []

    def scan_local_directories(self) -> List[ShipScanResult]:
        """Scan local directories for spacecraft models, CAD files, specs."""
        results = []
        scan_roots = [
            self.base_dir / "data" / "open_source",
            self.base_dir / "data" / "real_world",
            self.base_dir / "data" / "reference",
        ]
        for root in scan_roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".json", ".csv", ".txt", ".md", ".stl", ".obj"}:
                    rel = path.relative_to(self.base_dir)
                    try:
                        content = path.read_text(errors="ignore")[:2048]
                    except Exception:
                        content = ""
                    result = self._parse_file_content(path, content, "local")
                    if result:
                        results.append(result)
        return results

    def scan_github_repos(self, queries: List[str]) -> List[ShipScanResult]:
        """Search GitHub for open-source spacecraft models using gh CLI."""
        results = []
        for q in queries:
            try:
                out = subprocess.run(
                    ["gh", "search", "repos", q, "--limit", "10", "--json", "fullName,url,licenseInfo,description"],
                    capture_output=True, text=True, timeout=30
                ).stdout
                data = json.loads(out)
                for item in data:
                    license_name = item.get("licenseInfo", {}).get("name", "unknown") if item.get("licenseInfo") else "unknown"
                    is_open = any(k in (license_name or "").lower() for k in ["mit", "apache", "bsd", "gpl", "cc0", "public"])
                    results.append(ShipScanResult(
                        source="github",
                        name=item.get("fullName", q),
                        path_or_url=item.get("url", ""),
                        license=license_name,
                        copyright_status="open" if is_open else "restricted",
                        notes=item.get("description", "")[:200],
                        scan_timestamp=datetime.now().isoformat()
                    ))
            except Exception as e:
                results.append(ShipScanResult(
                    source="github",
                    name=f"scan_error:{q}",
                    path_or_url="",
                    license="error",
                    copyright_status="unknown",
                    notes=str(e),
                    scan_timestamp=datetime.now().isoformat()
                ))
        return results

    def scan_web_sources(self, urls: List[str]) -> List[ShipScanResult]:
        """Scan web sources for spacecraft technical data."""
        results = []
        for url in urls:
            try:
                # Use curl to fetch raw technical content
                out = subprocess.run(
                    ["curl", "-s", "--max-time", "15", url],
                    capture_output=True, text=True, timeout=20
                ).stdout[:4096]
                result = self._parse_file_content(Path(url), out, "web")
                if result:
                    result.path_or_url = url
                    results.append(result)
            except Exception as e:
                results.append(ShipScanResult(
                    source="web",
                    name=url.split("/")[-1] or url,
                    path_or_url=url,
                    license="unknown",
                    copyright_status="unknown",
                    notes=f"fetch error: {e}",
                    scan_timestamp=datetime.now().isoformat()
                ))
        return results

    def _parse_file_content(self, path: Path, content: str, source: str) -> Optional[ShipScanResult]:
        """Extract spacecraft specs from file content if present."""
        name = path.stem.replace("_", " ").replace("-", " ").title()
        mass_match = re.search(r"mass[:\s]+(\d+\.?\d*)\s*(kg|kg|t|tons?)", content, re.I)
        length_match = re.search(r"length[:\s]+(\d+\.?\d*)\s*(m|ft)", content, re.I)
        isp_match = re.search(r"isp[:\s]+(\d+\.?\d*)", content, re.I)
        thrust_match = re.search(r"thrust[:\s]+(\d+\.?\d*)\s*(n|kn|lbf)", content, re.I)
        speed_match = re.search(r"speed[:\s]+(\d+\.?\d*)\s*(m/s|c)", content, re.I)
        
        # Determine copyright status from filename/path
        path_str = str(path).lower()
        if any(k in path_str for k in ["public", "cc0", "mit", "apache", "bsd", "gpl", "open"]):
            status = "open"
        elif any(k in path_str for k in ["nasa", "esa", "gov", "public_domain"]):
            status = "public_domain"
        else:
            status = "unknown"
        
        result = ShipScanResult(
            source=source,
            name=name,
            path_or_url=str(path),
            license=status,
            copyright_status=status,
            mass_kg=float(mass_match.group(1)) if mass_match else None,
            length_m=float(length_match.group(1)) if length_match else None,
            isp_s=float(isp_match.group(1)) if isp_match else None,
            thrust_n=float(thrust_match.group(1)) if thrust_match else None,
            max_speed_m_s=float(speed_match.group(1)) if speed_match else None,
            scan_timestamp=datetime.now().isoformat()
        )
        return result

    def run_patrol(self, queries: List[str], urls: List[str]) -> Dict[str, Any]:
        """Execute full BDE patrol scan."""
        self.scan_log = []
        local_results = self.scan_local_directories()
        github_results = self.scan_github_repos(queries)
        web_results = self.scan_web_sources(urls)
        self.scan_log = local_results + github_results + web_results
        
        # Cache results
        cache_file = self.cache_dir / f"bde_patrol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with cache_file.open("w") as f:
            json.dump([asdict(r) for r in self.scan_log], f, indent=2)
        
        summary = {
            "total_scanned": len(self.scan_log),
            "local": len(local_results),
            "github": len(github_results),
            "web": len(web_results),
            "open_source": sum(1 for r in self.scan_log if r.copyright_status == "open"),
            "public_domain": sum(1 for r in self.scan_log if r.copyright_status == "public_domain"),
            "restricted": sum(1 for r in self.scan_log if r.copyright_status == "restricted"),
            "cache_file": str(cache_file),
        }
        return summary


DEFAULT_QUERIES = [
    "spacecraft CAD open source",
    "rocket engine design 3D model",
    "space shuttle CAD",
    "starship design open source",
    "satellite design filetype:stl",
    "rocket blueprint github",
    "spacecraft propulsion system design",
]

DEFAULT_URLS = [
    "https://raw.githubusercontent.com/nasa/nasa-design-docs/main/spacecraft/overview.md",
    "https://www.nasa.gov/sites/default/files/atoms/files/space_vehicle_design_v2.0.pdf",
]
