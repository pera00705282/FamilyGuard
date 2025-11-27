import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

class CodeFixer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.files_processed = 0
        self.issues_fixed = 0
        
    def fix_all_issues(self):
        """Fix all code style and import issues in the project"""
        print(f"🔍 Scanning {self.root_dir} for Python files...")
        
        # Process files in a specific order to handle dependencies
        file_patterns = [
            "**/base_*.py",  # Base classes first
            "**/base/*.py",
            "**/utils/*.py",
            "**/exchanges/*.py",
            "**/websocket/*.py",
            "**/examples/*.py"
        ]
        
        for pattern in file_patterns:
            for file_path in self.root_dir.glob(pattern):
                if file_path.is_file() and file_path.suffix == '.py':
                    self.fix_file_issues(file_path)
        
        print(f"\n✅ Fixed {self.issues_fixed} issues in {self.files_processed} files")
        
    def fix_file_issues(self, file_path: Path):
        """Fix issues in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Fix common issues
            content = self.fix_imports(content)
            content = self.fix_blank_lines(content)
            content = self.fix_whitespace(content)
            content = self.fix_trailing_whitespace(content)
            
            # Only write back if changes were made
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.files_processed += 1
                print(f"  ✓ Fixed issues in {file_path.relative_to(self.root_dir)}")
                
        except Exception as e:
            print(f"  ✗ Error processing {file_path.relative_to(self.root_dir)}: {e}")
    
    def fix_imports(self, content: str) -> str:
        """Fix import ordering and unused imports"""
        lines = content.splitlines()
        import_lines = []
        other_lines = []
        in_docstring = False
        
        # First pass: separate imports from other code
        for line in lines:
            stripped = line.strip()
            
            # Handle docstrings
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                other_lines.append(line)
                continue
                
            if in_docstring:
                other_lines.append(line)
                continue
                
            # Check for import statements
            if (stripped.startswith(('import ', 'from ')) and 
                not stripped.startswith(('import typing', 'from typing')) and
                not any(x in line for x in ['#', '"""', "'''"])):
                import_lines.append(line)
            else:
                other_lines.append(line)
        
        # Remove unused imports
        if import_lines:
            used_names = self.find_used_names(''.join(other_lines))
            import_lines = [imp for imp in import_lines if self.is_import_used(imp, used_names)]
        
        # Sort imports
        import_lines = self.sort_imports(import_lines)
        
        # Rebuild content
        result = []
        in_import_block = False
        
        for line in other_lines:
            stripped = line.strip()
            
            # Find where to insert imports
            if (not in_import_block and not stripped.startswith(('#', '"""', "'''")) and 
                not stripped.startswith('from __future__') and stripped):
                in_import_block = True
                result.extend([''] + import_lines + ['', ''])
                
            result.append(line.rstrip())
        
        return '\n'.join(result)
    
    def fix_blank_lines(self, content: str) -> str:
        """Fix blank lines between functions and classes"""
        lines = content.splitlines()
        result = []
        prev_line = None
        in_docstring = False
        
        for line in lines:
            stripped = line.strip()
            
            # Handle docstrings
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                result.append(line)
                continue
                
            if in_docstring:
                result.append(line)
                continue
                
            # Check for class/def
            if stripped.startswith(('class ', 'def ')) and prev_line and prev_line.strip():
                # Add two blank lines before class/def
                if not result[-1].strip() and len(result) > 1 and result[-2].strip():
                    result.append('')
                elif result and result[-1].strip():
                    result.extend(['', ''])
            
            result.append(line)
            prev_line = line
            
        return '\n'.join(result)
    
    def fix_whitespace(self, content: str) -> str:
        """Fix whitespace in blank lines"""
        lines = content.splitlines()
        return '\n'.join(line if line.strip() else '' for line in lines)
    
    def fix_trailing_whitespace(self, content: str) -> str:
        """Remove trailing whitespace"""
        return '\n'.join(line.rstrip() for line in content.splitlines())
    
    def find_used_names(self, content: str) -> Set[str]:
        """Find all used names in the code"""
        try:
            tree = ast.parse(content)
            used_names = set()
            
            class NameVisitor(ast.NodeVisitor):
                def visit_Name(self, node):
                    used_names.add(node.id)
                    
            NameVisitor().visit(tree)
            return used_names
        except:
            return set()
    
    def is_import_used(self, import_line: str, used_names: Set[str]) -> bool:
        """Check if an import is actually used"""
        if import_line.startswith('from '):
            # from module import name1, name2
            match = re.match(r'from\s+(\S+)\s+import\s+(.+)', import_line)
            if match:
                module, names = match.groups()
                for name in re.split(r'\s*,\s*', names):
                    name = name.split(' as ')[0].strip()  # Handle aliases
                    if name in used_names:
                        return True
                return False
        else:
            # import module or import module as alias
            match = re.match(r'import\s+(\S+)', import_line)
            if match:
                module = match.group(1).split(' as ')[0].strip()
                return module in used_names or any(
                    name.startswith(f"{module}.") for name in used_names
                )
        return True  # If we can't parse it, assume it's used
    
    def sort_imports(self, imports: List[str]) -> List[str]:
        """Sort imports alphabetically"""
        return sorted(imports, key=lambda x: (
            x.startswith('from '),  # Group 'from' imports after 'import'
            x.lower()
        ))

if __name__ == "__main__":
    print("🛠️  Starting code style fixes...")
    fixer = CodeFixer(os.getcwd())
    fixer.fix_all_issues()
    print("✨ All done!")