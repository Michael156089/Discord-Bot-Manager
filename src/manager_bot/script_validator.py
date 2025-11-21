# Phase 3: Script Validation System
# File: src/manager_bot/script_validator.py

import ast
import os

DANGEROUS_IMPORTS = {
    'subprocess', 'os.system', 'eval', 'exec', 
    '__import__', 'compile', 'open',
    'shutil.rm', 'pathlib.Path.unlink'
}

DANGEROUS_FUNCTIONS = {
    'exec', 'eval', '__import__', 'compile',
    'system', 'popen', 'spawn'
}


class ScriptValidator(ast.NodeVisitor):
    """AST visitor to detect dangerous code patterns."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def visit_Import(self, node):
        """Check for dangerous imports."""
        for alias in node.names:
            if any(dangerous in alias.name for dangerous in DANGEROUS_IMPORTS):
                self.issues.append(f"Ligne {node.lineno}: Import dangereux '{alias.name}'")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Check for dangerous from-imports."""
        if node.module:
            if any(dangerous in node.module for dangerous in DANGEROUS_IMPORTS):
                self.issues.append(f"Ligne {node.lineno}: Import dangereux 'from {node.module}'")
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Check for dangerous function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id in DANGEROUS_FUNCTIONS:
                self.issues.append(f"Ligne {node.lineno}: Fonction dangereuse '{node.func.id}()'")
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in DANGEROUS_FUNCTIONS:
                self.warnings.append(f"Ligne {node.lineno}: Fonction potentiellement dangereuse '.{attr_name}()'")
        self.generic_visit(node)


def validate_script(script_path: str) -> tuple[bool, list, list]:
    """
    Validate a Python script for dangerous code.
    Returns (is_safe, issues, warnings).
    """
    if not os.path.exists(script_path):
        return False, [f"Fichier introuvable: {script_path}"], []
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = ast.parse(code, filename=script_path)
        
        validator = ScriptValidator()
        validator.visit(tree)
        
        is_safe = len(validator.issues) == 0
        
        return is_safe, validator.issues, validator.warnings
        
    except SyntaxError as e:
        return False, [f"Erreur de syntaxe ligne {e.lineno}: {e.msg}"], []
    except Exception as e:
        return False, [f"Erreur de validation: {str(e)}"], []


def validate_user_script_before_start(user_id: int, script_name: str, scripts_dir: str) ->tuple[bool, str]:
    """
    Validate a user script before starting the bot.
    Returns (is_valid, error_message).
    """
    script_path = os.path.join(scripts_dir, script_name)
    
    is_safe, issues, warnings = validate_script(script_path)
    
    if not is_safe:
        error_msg = "❌ Script refusé (code dangereux détecté):\n"
        error_msg += "\n".join(f"  - {issue}" for issue in issues)
        return False, error_msg
    
    if warnings:
        print(f"⚠️ Avertissements pour '{script_name}':")
        for warning in warnings:
            print(f"  - {warning}")
    
    return True, ""
