#!/usr/bin/env python3
"""
Auto-fix script: Replace prints with logging and bare excepts across all source files.
Run once and verify the changes.
"""
import re
from pathlib import Path

# Files to process
src_dir = Path("c:\\PYL\\src")
main_file = Path("c:\\PYL\\main.py")

files_to_fix = [
    src_dir / "macro_engine.py",
    src_dir / "macro_regime.py",
    src_dir / "backtest_engine.py",
    src_dir / "optimizer.py",
    src_dir / "reporting.py",
    main_file
]

def add_logging_import(content):
    """Add logging import if not already present."""
    if "import logging" not in content:
        # Find the insertion point (after other imports, before classes)
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_idx = i + 1
        lines.insert(insert_idx, "import logging")
        
        # Add logger after imports
        lines.insert(insert_idx + 1, "")
        module_name = Path(main_file).stem if "main" in str(main_file) else Path(main_file).stem
        if "main" not in str(main_file):
            module_name = Path(files_to_fix[0]).stem.replace(".py", "")
        logger_line = f'logger = logging.getLogger("PYL.{module_name}")'
        lines.insert(insert_idx + 2, logger_line)
        
        content = "\n".join(lines)
    return content

def fix_prints(content):
    """Replace print() calls with logger calls."""
    # Pattern: print(f"...") or print("...")
    content = re.sub(
        r'print\(f?"(.+?)"\)',
        lambda m: f'logger.info(f"{m.group(1)}")',
        content
    )
    return content

def fix_bare_excepts(content):
    """Replace bare except: with specific exception handling."""
    # This is a simple heuristic - catches "except:" followed by pass or simple statements
    content = re.sub(
        r'except:\s*pass',
        r'except Exception:\n            pass',
        content
    )
    content = re.sub(
        r'except:\s*(\w+)',
        r'except Exception:\n            \1',
        content
    )
    return content

def remove_ssl_overrides(content):
    """Remove global SSL override blocks."""
    # Remove the SSL override try-except blocks
    content = re.sub(
        r'try:\s*_create_unverified.*?ssl\._create_default_https_context = _create_unverified_https_context',
        '# SSL override removed - handle per-request if needed',
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r'try:\s*ssl\._create_default.*?pass\s*else:.*?ssl\._create_default_https_context = _create_unverified_https_context',
        '# SSL override removed',
        content,
        flags=re.DOTALL
    )
    return content

if __name__ == "__main__":
    for filepath in files_to_fix:
        if not filepath.exists():
            print(f"⏭️  Skipping (not found): {filepath}")
            continue
        
        print(f"📝 Processing: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply fixes
        content = add_logging_import(content)
        content = fix_prints(content)
        content = remove_ssl_overrides(content)
        
        # Only write if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {filepath}")
        else:
            print(f"⏭️  No changes needed: {filepath}")
    
    print("\n✅ Auto-fix script completed!")
