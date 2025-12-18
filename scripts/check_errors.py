#!/usr/bin/env python3
"""
Script สำหรับตรวจสอบ Errors ใน Python Code

Usage:
    python3 scripts/check_errors.py [file_or_directory]
    
Examples:
    python3 scripts/check_errors.py app/services/whisper_providers/faster_whisper_provider.py
    python3 scripts/check_errors.py app/
    python3 scripts/check_errors.py  # Check all Python files
"""

import os
import sys
import ast
import py_compile
from pathlib import Path
from typing import List, Tuple

def check_syntax(file_path: str) -> Tuple[bool, str]:
    """ตรวจสอบ syntax errors"""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, "OK"
    except py_compile.PyCompileError as e:
        return False, str(e)

def check_ast(file_path: str) -> Tuple[bool, str]:
    """ตรวจสอบ AST parsing"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, "OK"
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_import(file_path: str) -> Tuple[bool, str]:
    """ตรวจสอบ import (อาจล้มเหลวถ้าไม่มี dependencies)"""
    try:
        # Convert file path to module name
        rel_path = os.path.relpath(file_path, os.getcwd())
        module_name = rel_path.replace('/', '.').replace('\\', '.').replace('.py', '')
        
        # Add current directory to path
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        
        __import__(module_name)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax Error: Line {e.lineno}: {e.msg}"
    except ImportError as e:
        return False, f"Import Error (อาจเป็นเพราะ dependencies): {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def find_python_files(path: str) -> List[str]:
    """หาไฟล์ Python ทั้งหมด"""
    python_files = []
    path_obj = Path(path)
    
    if path_obj.is_file():
        if path_obj.suffix == '.py':
            python_files.append(str(path_obj))
    elif path_obj.is_dir():
        for py_file in path_obj.rglob('*.py'):
            # Skip __pycache__ and .pyc files
            if '__pycache__' not in str(py_file):
                python_files.append(str(py_file))
    
    return sorted(python_files)

def main():
    """Main function"""
    print("=" * 80)
    print("🔍 Python Code Error Checker")
    print("=" * 80)
    
    # Get target path
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "app/"
    
    if not os.path.exists(target):
        print(f"❌ Path not found: {target}")
        sys.exit(1)
    
    # Find Python files
    python_files = find_python_files(target)
    
    if not python_files:
        print(f"⚠️  No Python files found in: {target}")
        sys.exit(0)
    
    print(f"\n📋 Found {len(python_files)} Python file(s)")
    print("-" * 80)
    
    # Check each file
    errors_found = False
    for file_path in python_files:
        print(f"\n📄 {file_path}")
        
        # Syntax check
        syntax_ok, syntax_msg = check_syntax(file_path)
        if syntax_ok:
            print(f"   ✅ Syntax: OK")
        else:
            print(f"   ❌ Syntax: {syntax_msg}")
            errors_found = True
        
        # AST check
        ast_ok, ast_msg = check_ast(file_path)
        if ast_ok:
            print(f"   ✅ AST: OK")
        else:
            print(f"   ❌ AST: {ast_msg}")
            errors_found = True
        
        # Import check (optional - may fail due to dependencies)
        import_ok, import_msg = check_import(file_path)
        if import_ok:
            print(f"   ✅ Import: OK")
        else:
            print(f"   ⚠️  Import: {import_msg}")
    
    print("\n" + "=" * 80)
    if errors_found:
        print("❌ Errors found!")
        sys.exit(1)
    else:
        print("✅ No syntax errors found!")
        sys.exit(0)

if __name__ == "__main__":
    main()

