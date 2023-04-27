from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union, Tuple, Callable
from contextlib import suppress

from my_semantic_baza import TYPE_CONVERTIBILITY, \
    TypeDesc, IdentDesc, IdentScope, SemanticException


class AstNode(ABC):

    def __init__(self, row: Optional[int] = None, **props) -> None:
        super().__init__()
        self.row = row
        for k, v in props.items(): # паттерн контейнер свойств: получаем словарь свойств и добавляем их в класс
            setattr(self, k, v)
        # здесь надо будет потом понять, является ли узел идентификатором или типом объявления
        self.node_type: Optional[TypeDesc] = None 
        self.node_ident: Optional[IdentDesc] = None 

    @property
    def childs(self)->Tuple['AstNode', ...]:
        return ()

    @abstractmethod
    def __str__(self)->str:
        pass

    def to_str(self):
        return str(self)

    def to_str_full(self):
        r = ''
        if self.node_ident:
            r = str(self.node_ident)
        elif self.node_type:
            r = str(self.node_type)
        return self.to_str() + (' : ' + r if r else '') # в конце через : добавляется тип или идентификатор

    def semantic_error(self, message: str):
            raise SemanticException(message, self.row)

    @property
    def tree(self):
        res = [str(self)]
        childs = self.childs
        for i, child in enumerate(childs):
            ch0, ch = '├', '│'
            if i == len(childs) - 1:
                ch0, ch = '└', ' '
            res.extend(((ch0 if j == 0 else ch) + ' ' + s for j, s in enumerate(child.tree)))
        return res

    def visit(self, func: Callable[['AstNode'], None])->None: # кусочек реализации паттерна посетитель
        func(self)
        map(func, self.childs) # посещаем все поддерева

    def __getitem__(self, index): # я так понял, это переопределение операции индексирования
        return self.childs[index] if index < len(self.childs) else None


class ValueNode(AstNode):
    pass


class LiteralNode(ValueNode):
    def __init__(self, literal: str, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.literal = literal
        self.value = eval(literal)

    def __str__(self) -> str:
        return f'{self.literal}'


class IdentNode(ValueNode):
    def __init__(self, name: str, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.name = str(name)

    def __str__(self)->str:
        return str(self.name)


class BinOp(Enum):
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = '%'
    GT = '>'
    LT = '<'
    GE = '>='
    LE = '<='
    EQ = '=='
    NE = '!='
    AND = '&&'
    OR = '||'

    def __str__(self) -> str:
        return str(self.value)


class BinOpNode(ValueNode):
    def __init__(self, op: BinOp, arg1: ValueNode, arg2: ValueNode, 
                 row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2

    @property
    def childs(self) -> Tuple[ValueNode, ValueNode]:
        return self.arg1, self.arg2

    def __str__(self)->str:
        return str(self.op.value)


class StatementNode(AstNode):
    pass


class _GroupNode(AstNode):
    """Класс для группировки других узлов (вспомогательный, в синтаксисе нет соотвествия)
    """

    def __init__(self, name: str, *childs: AstNode,
                 row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.name = name
        self._childs = childs

    def __str__(self) -> str:
        return self.name

    @property
    def childs(self) -> Tuple['AstNode', ...]:
        return self._childs


class DeclTypeNode(IdentNode):
    """Класс для представления типов данных
    """

    def __init__(self, name: str,
                 row: Optional[int] = None, **props) -> None:
        super().__init__(name, row=row, **props)
        self.type = None
        # пытаемся создать тип данных
        with suppress(SemanticException):
            self.type = TypeDesc.from_str(name)

    def to_str_full(self):
        return self.to_str()


class TypeConvertNode(ValueNode):
    """Класс для представления в AST-дереве операций конвертации типов данных
    """

    def __init__(self, expr: ValueNode, type_: TypeDesc,
                 row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.expr = expr
        self.type = type_
        self.node_type = type_

    def __str__(self) -> str:
        return 'convert'

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (_GroupNode(str(self.type), self.expr), )


class AssignNode(StatementNode):
    def __init__(self, var: IdentNode, val: ValueNode, 
                 row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.var = var
        self.val = val

    @property
    def childs(self) -> Tuple[IdentNode, ValueNode]:
        return (self.var, self.val)

    def __str__(self)->str:
        return '='


class StatementListNode(StatementNode):
    def __init__(self, *exprs: AstNode, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.exprs = exprs
        self.program = False

    @property
    def childs(self) -> Tuple[AstNode]:
        return self.exprs

    def __str__(self)->str:
        return '...'


class IfOpNode(StatementNode):
    def __init__(self, cond: ValueNode, thenStmts, elseStmts = None, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.cond = cond
        self.thenStmts = thenStmts
        self.elseStmts = elseStmts

    @property
    def childs(self)->Tuple[AstNode, ...]:
        if self.elseStmts == None:
            return (self.cond, self.thenStmts)
        else:
            return (self.cond, self.thenStmts, self.elseStmts)

    def __str__(self) -> str:
        return 'if'


class WhileOpNode(StatementNode):
    def __init__(self, cond: ValueNode, stmts, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.cond = cond
        self.stmts = stmts

    @property
    def childs(self)->Tuple[AstNode, ...]:
       return (self.cond, self.stmts) 

    def __str__(self) -> str:
        return 'while'


class ForOpNode(StatementNode):
    def __init__(self, decls=StatementListNode(), cond=LiteralNode('1'), stmt=StatementListNode(), body=StatementListNode(), 
                 row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.decl = decls
        self.cond = cond
        self.stmt = stmt
        self.body = body

    @property
    def childs(self)->Tuple[AstNode, ...]:
        return (self.decl, self.cond, self.stmt, self.body)

    def __str__(self) -> str:
        return 'for'


class DeclNode(StatementNode):
    def __init__(self, decl_type: DeclTypeNode, ident: IdentNode, init_value=None, 
                 row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.decl_type = decl_type
        self.ident = ident
        self.init_value = init_value

    @property
    def childs(self) -> Tuple[IdentNode, ...]:
        if self.init_value == None:
            return self.ident,
        else:
            return (self.ident, self.init_value)

    def __str__(self) -> str:
        return f'variable: {self.decl_type}'


class DeclListNode(AstNode):
    def __init__(self, *params: DeclNode, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.params = params

    @property
    def childs(self) -> Tuple[DeclNode]:
        return self.params

    def __str__(self)->str:
        return 'params'


class FuncDeclNode(StatementNode):
    def __init__(self, func_type: DeclTypeNode, name, params: DeclListNode, body, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.func_type = func_type
        self.name = name
        self.params = params
        self.body = body

    @property
    def childs(self) -> Tuple['AstNode', ...]:
        if self.params == None:
            return (self.func_type, self.name, self.body)
        else:
            return (self.func_type, self.name, self.params, self.body)

    def __str__(self) -> str:
        return f'fn -> {self.func_type}'


class FuncCallNode(StatementNode):
    def __init__(self, name: IdentNode, params=None, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.name = name
        self.params = params

    @property
    def childs(self) -> Tuple['AstNode', ...]:
        if self.params == None:
            return self.name, 
        else:
            return (self.name, self.params)
    
    def __str__(self) -> str:
        return str(self.name)


class ReturnOpNode(StatementNode):
    def __init__(self, value = None, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.value = value

    @property
    def childs(self) -> Tuple[AstNode]:
        return self.value,

    def __str__(self) -> str:
        return 'return'
    
EMPTY_STMT = StatementListNode()
EMPTY_IDENT = IdentDesc('', TypeDesc.VOID)
