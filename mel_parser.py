from typing import BinaryIO
from parser_base import *
from mel_ast import *


class MELError(Exception):
    """Класс для исключений интерпретатора"""

    def __init__(self, message):
        super().__init__(message)


class MELParser(BaseParser):
    """Простейший интерпретатор C подобного языка.
    Вычисления производятся в процессе разбора

    Грамматика:
        num   -> <число>
        ident -> <идентификатор>
        group -> num | ident | '(' add ')'
        mult  -> group (('*' | '/') group)*
        add   -> mult (('+' | '-') mult)*
        bool  -> group (('==' | '!=' | '>=' | '<=' | '>' | '<') group)*
        comp -> bool (('&&' | '||' ) bool)*
        expr  -> add
        decl  -> 'type' ident ( = expr )?
        params -> decl (, decl)*
        fn    -> 'fn' ident ( params): 'type' { state }
        return -> 'return' expr
        state -> 'input' ident | 'output' add | decl | if | while | for | ident '=' add | fn | ident(params*)
        if    -> 'if' ( comp ) { state ('else' { state) } 
        while -> 'while' ( comp ) { expr_list } 
        for   -> 'for' (decl; comp; expr) { state }
        prog  -> state*
        start -> prog
    """

    def __init__(self, text: str):
        """Конструктор
        :param text: текст программы
        """
        super().__init__(text)

    def num(self)->NumNode:
        """num   -> <число>"""
        self._ws()
        pos = self.pos
        while self._curr.isdecimal() or self._curr == '.':
            self.pos += 1
        res = NumNode(float(self.text[pos:self.pos]))
        self._ws()
        return res

    def ident(self)->IdentNode:
        """ident -> <идентификатор>"""
        self._ws()
        pos = self.pos
        while self._curr.isalnum():
            self.pos += 1
        res = IdentNode(self.text[pos:self.pos])
        self._ws()
        return res

    def group(self)->ValueNode:
        """group -> num | ident | '(' add ')'"""
        if self._is_parse('('):
            self._parse('(')
            res = self.add()
            self._parse(')')
            return res
        elif self._curr.isdecimal() or self._curr == '.':
            return self.num()
        else:
            return self.ident()

    def mult(self)->BinOpNode:
        """mult  -> group (('*' | '/') group)*"""
        res = self.group()
        while self._is_parse('*', '/'):
            op = self._parse('*', '/')
            tmp = self.group()
            res = BinOpNode(BinOp(op), res, tmp)
        return res

    def add(self)->BinOpNode:
        """add   -> mult (('+' | '-') mult)*"""
        res = self.mult()
        while self._is_parse('+', '-'):
            op = self._parse('+', '-')
            tmp = self.mult()
            res = BinOpNode(BinOp(op), res, tmp)
        return res

    def _bool(self)->BinOpNode:
        """bool  -> group (('==' | '!=' | '>=' | '<=' | '>' | '<') group)*"""
        res = self.group()
        while self._is_parse('==', '!=','>=' , '<=' , '>' , '<'):
            op = self._parse('==', '!=','>=' , '<=' , '>' , '<')
            op2 = self.group()
            res = BinOpNode(BinOp(op), res, op2)
        return res

    def comp(self)->BinOpNode: 
        """comp -> bool (('&&' | '||' ) bool)*"""
        res = self._bool()
        while self._is_parse('||', '&&'):
            op = self._parse('||', '&&')
            op2 = self._bool()
            res = BinOpNode(BinOp(op), res, op2)
        return res

    def _is_decl_type(self):
        return self._is_parse('int', 'float', 'double', 'char', 'string')

    def decl(self)->DeclNode:
        """decl  -> 'type' ident ( = expr )?"""
        d_type = self._parse('int', 'float', 'double', 'char', 'string')
        var = self.ident()
        init = None
        if self._is_parse('='):
            self._parse('=')
            init = self.expr()
        return DeclNode(DeclType(d_type), var, init)

    def params(self)->DeclNodeList:
        """params -> decl (, decl)*"""
        res = []
        res.append(self.decl())
        while self._is_parse(','):
            self._parse(',')
            self._ws()
            res.append(self.decl())
        return DeclNodeList(*res)

    def fn(self)-> AstNode:
        self._parse('fn')
        name = self.ident()
        self._parse('(')
        param = self.params()
        self._parse('):')
        func_type = self._parse('int', 'float', 'double', 'char', 'string', 'void')
        self._parse('{')
        func_body = self.state()
        self._parse('}')
        return FuncDeclNode(FuncDeclType(func_type), name, param, func_body)

    def fn_call(self, ident) -> AstNode:
        self._parse('(')
        if self._is_parse(')'):
            self._parse(')')
            return FuncCallNode(ident)
        params = [self.expr()]
        while self._is_parse(','):
            self._parse(',')
            self._ws()
            params.append(self.expr())
        self._parse(')')
        return FuncCallNode(ident, ExprListNode(*params))

    def _return(self)->AstNode:
        self._parse('return')
        val = self.expr()
        return ReturnNode(val)

    def state(self)->AstNode:
        """state  -> 'input' ident | 'output' add | decl | if | while | for | ident '=' add | ident(expr*)"""
        if self._is_parse('input', 'output'):
            op = self._parse('input', 'output')
            if op == 'input':
                return InputNode(self.ident())
            else:
                return OutputNode(self.add())
        elif self._is_decl_type():
            return self.decl()
        elif self._is_parse('fn'):
            return self.fn()
        elif self._is_parse('if'):
            return self._if()
        elif self._is_parse('while'):
            return self._while()
        elif self._is_parse('for'):
            return self._for()
        elif self._is_parse('return'):
            return self._return()
        else:
            var = self.ident()
            if self._is_parse('('):
                return self.fn_call(var)
            else:
                self._parse('=')
                return AssignNode(var, self.add())

    def _if(self) -> AstNode:
        """if    -> 'if' ( expr ) state ('else' state)"""
        self._parse('if')
        self._parse('(')
        res_expr = self.comp()
        self._parse(')')
        self._parse('{')
        then_state = self.state()
        self._parse('}')
        else_state = None
        if self._is_parse('else'):
            self._parse('else')
            self._parse('{')
            else_state = self.state()
            self._parse('}')
        return IfNode(res_expr, then_state, else_state)

    def _while(self) -> AstNode:
        """while -> 'while' ( expr ) { stmt }"""
        self._ws()
        self._parse('while')
        self._parse('(')
        res_expr = self.comp()
        self._parse(')')
        self._parse('{')
        loop_body = self.state()
        self._parse('}')
        return WhileNode(res_expr, loop_body)

    def _for(self)->AstNode:
        """for   -> 'for' (decl; comp; expr) { state }"""
        self._ws()
        self._parse('for')
        self._parse('(')
        res_decl = self.state()
        self._parse(';')
        res_comp = self.comp()
        self._parse(';')
        res_expr = self.expr()
        self._parse(')')
        self._parse('{')
        loop_body = self.state()
        self._parse('}')
        return ForNode(res_decl, res_comp, res_expr, loop_body)
        

    def expr(self)->BinOpNode:
        return self.add()

    def prog(self)->ExprListNode:
        """prog  -> state*"""
        states = []
        self._ws()
        while self._curr != '$':
            states.append(self.state())
        return ExprListNode(*states)

    def start(self)->ExprListNode:
        """start -> prog"""
        return self.prog()

    @classmethod
    def parse(cls, prog: str)->ExprListNode:
        parser = cls(str(prog))
        return parser.start()
