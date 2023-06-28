from abc import ABC, abstractmethod
from typing import Any, Optional, Union, Tuple, Callable, List
from contextlib import suppress

from my_semantic_baza import TYPE_CONVERTIBILITY, \
    TypeDesc, IdentDesc, IdentScope, SemanticException, BIN_OP_TYPE_COMPATIBILITY, ScopeType
from binop import BinOp


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
    def __str__(self) -> str:
        pass

    def semantic_check(self, scope: IdentScope):
        pass

    def to_str(self):
        return str(self)

    def to_str_full(self):
        r = ''
        if self.node_type:
            r = str(self.node_type)
        if self.node_ident:
            r += ', ' + str(self.node_ident)
        return self.to_str() + (' => ' + r if r else '') # в конце через : добавляется тип или идентификатор

    def semantic_error(self, message: str):
            raise SemanticException(message, self.row)

    @property
    def tree(self):
        res = [self.to_str_full()]
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

    def semantic_check(self, scope: IdentScope):
        # пытаемся определить тип литерала
        if isinstance(self.value, int):
            self.node_type = TypeDesc.INT
        elif isinstance(self.value, float):
            self.node_type = TypeDesc.FLOAT
        elif isinstance(self.value, str):
            if self.literal[0] == '"':
                self.node_type = TypeDesc.STR
            else:
                self.node_type = TypeDesc.CHAR
        else:
            self.semantic_error('Неизвестный тип ' + str(type(self.value)) + ' для ' + str(self.value))
    def __str__(self) -> str:
        return f'{self.literal}'


def type_convert(expr: ValueNode, type_: TypeDesc, except_self: Optional[AstNode] = None, comment: Optional[str] = None) -> ValueNode:
    """Метод преобразования ExprNode узла AST-дерева к другому типу
    :param expr: узел AST-дерева
    :param type_: требуемый тип
    :param except_self: узел, о которого будет исключение
    :param comment: комментарий
    :return: узел AST-дерева c операцией преобразования
    """

    if expr.node_type is None:
        except_self.semantic_error('Тип выражения не определен')
    if expr.node_type == type_: # если типы одни и те же
        return expr
    # если типы простые и все четко конвертируется
    if expr.node_type.is_simple and type_.is_simple and \
            expr.node_type.base_type in TYPE_CONVERTIBILITY and type_.base_type in TYPE_CONVERTIBILITY[expr.node_type.base_type]:
        return TypeConvertNode(expr, type_)
    else:
        (except_self if except_self else expr).semantic_error('Тип {0}{2} не конвертируется в {1}'.format(
            expr.node_type, type_, ' ({})'.format(comment) if comment else ''
        ))


class IdentNode(ValueNode):
    def __init__(self, name: str, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.name = str(name)

    def semantic_check(self, scope: IdentScope):
        ident = scope.get_ident(self.name) # ищем данное объявление в местной области видимости
        if ident is None:
            self.semantic_error('Идентификатор ' + str(self.name) + ' не найден')
        self.node_type = ident.type # в качестве типа узла присваиваем тип идентификатора
        self.node_ident = ident     # и сам идентификатор

    def __str__(self)->str:
        return str(self.name)



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

    def semantic_check(self, scope: IdentScope):
        # проверяем каждый аргумент
        self.arg1.semantic_check(scope)
        self.arg2.semantic_check(scope)

        if self.arg1.node_type.is_simple or self.arg2.node_type.is_simple: # если один из аргументов представляет собой простой тип
            compatibility = BIN_OP_TYPE_COMPATIBILITY[self.op] # находим типы, которые между собой могут взаимодействовать
            args_types = (self.arg1.node_type.base_type, self.arg2.node_type.base_type)
            if args_types in compatibility:
                self.node_type = TypeDesc.from_base_type(compatibility[args_types]) # если с типами все ок, устанавливаем итоговый тип выражения
                return

            if self.arg2.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg2_type in TYPE_CONVERTIBILITY[self.arg2.node_type.base_type]:
                    args_types = (self.arg1.node_type.base_type, arg2_type)
                    if args_types in compatibility:
                        self.arg2 = type_convert(self.arg2, TypeDesc.from_base_type(arg2_type))
                        self.node_type = TypeDesc.from_base_type(compatibility[args_types])
                        return
            if self.arg1.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg1_type in TYPE_CONVERTIBILITY[self.arg1.node_type.base_type]:
                    args_types = (arg1_type, self.arg2.node_type.base_type)
                    if args_types in compatibility:
                        self.arg1 = type_convert(self.arg1, TypeDesc.from_base_type(arg1_type))
                        self.node_type = TypeDesc.from_base_type(compatibility[args_types])
                        return

        self.semantic_error("Оператор {} не применим к типам ({}, {})".format(
            self.op, self.arg1.node_type, self.arg2.node_type
        ))


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

    def semantic_check(self, scope: IdentScope):
        if self.type is None:
            self.semantic_error('Неизвестный ' + str(self.name) + ' тип')
        self.node_type = self.type

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
    def __init__(self, var: StatementNode, val: ValueNode, 
                 row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.var = var
        self.val = val

    @property
    def childs(self) -> Tuple[StatementNode, ValueNode]:
        return (self.var, self.val)

    def semantic_check(self, scope: IdentScope):
        self.var.semantic_check(scope)
        self.val.semantic_check(scope)
        self.val = type_convert(self.val, self.var.node_type, self, 'присваиваемое значение')
        self.node_type = self.var.node_type


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

    def semantic_check(self, scope: IdentScope):
        if not self.program:
            scope = IdentScope(scope)
        for stmt in self.exprs:
            stmt.semantic_check(scope)
        self.node_type = TypeDesc.VOID


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

    def semantic_check(self, scope: IdentScope):
        self.cond.semantic_check(scope)
        self.cond = type_convert(self.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        self.thenStmts.semantic_check(IdentScope(scope))
        if self.elseStmts:
            self.elseStmts.semantic_check(IdentScope(scope))
        self.node_type = TypeDesc.VOID

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

    def semantic_check(self, scope: IdentScope):
        self.cond.semantic_check(scope)
        self.cond = type_convert(self.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        self.stmts.semantic_check(IdentScope(scope))
        self.node_type = TypeDesc.VOID

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

    def semantic_check(self, scope: IdentScope):
        scope = IdentScope(scope)
        self.decl.semantic_check(scope) # проверяем объявления
        if self.cond == EMPTY_STMT:
            self.cond = LiteralNode('1')
        self.cond.semantic_check(scope) # проверяем условие
        self.cond = type_convert(self.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        self.stmt.semantic_check(scope) # проверяем выражения в заголовке цикла
        self.body.semantic_check(IdentScope(scope))
        self.node_type = TypeDesc.VOID

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

    def semantic_check(self, scope: IdentScope):
        self.decl_type.semantic_check(scope)
        try:
            scope.add_ident(IdentDesc(self.ident.name, self.decl_type.type))
        except SemanticException as e:
            self.semantic_error(e.message)
        self.ident.semantic_check(scope)
        if self.init_value != None:
            self.init_value.semantic_check(scope)
        self.node_type = TypeDesc.VOID

    def __str__(self) -> str:
        return f'variable: {self.decl_type}'


class ArrNode(StatementNode):
    """
    Узел объявления самого массива в программе
    """
    def __init__(self, arr_type: DeclTypeNode, name: IdentNode, length: ValueNode, *elements: ValueNode,
                 row: Optional[int] = None, **props) -> None:
        super().__init__(row, **props)
        self.arr_type = arr_type
        self.name = name
        self.length = length
        self.elements = elements

    @property
    def childs(self) -> Tuple[ValueNode]:
        return self.elements

    def __str__(self) -> str:
        return "array: {}".format(self.name)

    def semantic_check(self, scope: IdentScope):
        self.arr_type.semantic_check(scope)
        for element in self.elements:
            element.semantic_check(scope)
        try:
            scope.add_ident(IdentDesc(self.name.name, self.arr_type.type))
        except SemanticException as e:
            self.semantic_error(e.message)


class ArrItemNode(ValueNode):
    """
    Обращение к элементу массива по индексу
    """
    def __init__(self, ident: IdentNode, index: ValueNode, row: Optional[int] = None, **props) -> None:
        super().__init__(row, **props)
        self.ident = ident
        self.index = index
        self.type = None

    @property
    def childs(self) -> Tuple['AstNode', ...]:
        return self.index,

    def __str__(self) -> str:
        return "arr \"{}\" item".format(self.ident)

    def semantic_check(self, scope: IdentScope):
        arr = scope.get_ident(self.ident.name)
        if arr is None:
            self.semantic_error('Массив {} не найден'.format(self.ident.name))
        self.node_type = arr.type


class DeclListNode(AstNode):
    def __init__(self, *params: DeclNode, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.params = params

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.params

    def semantic_check(self, scope: IdentScope):
        for param in self.params:
            param.semantic_check(scope)
            param.ident.node_ident = scope.add_ident(IdentDesc(param.ident.name, param.decl_type.type, ScopeType.PARAM))
        self.node_type = TypeDesc.VOID

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

    def semantic_check(self, scope: IdentScope):
        if scope.curr_func:
            self.semantic_error("Объявление функции ({}) внутри другой функции не поддерживается".format(self.name.name))
        parent_scope = scope
        self.func_type.semantic_check(scope) # проверяем возвращаемый тип
        scope = IdentScope(scope)
        scope.func = EMPTY_IDENT  # делаем так, что текущая функция не входит в другую функцию
        self.params.semantic_check(scope)


        params: List[TypeDesc] = [] # начинаем перебирать параметры
        for param in self.params.params:
            params.append(param.decl_type.type)
            # scope.add_ident(IdentDesc(param.ident.name, param.decl_type.type))

        type_ = TypeDesc(None, self.func_type.type, tuple(params))
        func_ident = IdentDesc(self.name.name, type_)
        scope.func = func_ident
        self.name.node_type = type_
        try:
            self.name.node_ident = parent_scope.curr_global.add_ident(func_ident)
        except SemanticException as e:
            self.name.semantic_error("Повторное объявление функции {}".format(self.name.name))
        self.body.semantic_check(scope)
        self.node_type = TypeDesc.VOID


    def __str__(self) -> str:
        return f'fn -> {self.func_type}'


class ValueListNode(AstNode):
    def __init__(self, *params: ValueNode, row: Optional[int] = None, **props):
        super().__init__(row=row, **props)
        self.params = params

    @property
    def childs(self) -> Tuple[ValueNode]:
        return self.params

    def semantic_check(self, scope: IdentScope):
        for param in self.params:
            param.semantic_check(scope)
        self.node_type = TypeDesc.VOID

    def __str__(self) -> str:
        return 'params'


class FuncCallNode(StatementNode):
    def __init__(self, name: IdentNode, params: ValueListNode, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.name = name
        self.params = params

    @property
    def childs(self) -> Tuple['AstNode', ...]:
        if self.params == None:
            return self.name,
        else:
            return (self.name, self.params)

    def semantic_check(self, scope: IdentScope):
        func = scope.get_ident(self.name.name) # получаем объект идентификатора функции
        if func is None:
            self.semantic_error('Функция {} не найдена'.format(self.name.name))
        if not func.type.func: # если данный идентификатор не функция 
            self.semantic_error('Идентификатор {} не является функцией'.format(func.name))
        if len(func.type.params) != len(self.params.params):
            self.semantic_error('Кол-во аргументов {} не совпадает (ожидалось {}, передано {})'.format(
                func.name, len(func.type.params), len(self.params)
            ))
        params = []
        error = False
        decl_params_str = fact_params_str = ''
        for i in range(len(self.params.params)):
            param: ValueNode = self.params[i] # вытаскиваем какое то rvalue значение или expr
            param.semantic_check(scope)
            if len(decl_params_str) > 0:
                decl_params_str += ', '
            decl_params_str += str(func.type.params[i])
            if len(fact_params_str) > 0:
                fact_params_str += ', '
            fact_params_str += str(param.node_type)
            try:
                params.append(type_convert(param, func.type.params[i]))
            except:
                error = True
        if error:
            self.semantic_error('Фактические типы ({1}) аргументов функции {0} не совпадают с формальными ({2})\
                                            и не приводимы'.format(
                func.name, fact_params_str, decl_params_str
            ))
        else:
            self.params.params = params
            self.name.node_type = func.type
            self.name.node_ident = func
            self.node_type = func.type.return_type
    
    def __str__(self) -> str:
        return str(self.name)


class ReturnOpNode(StatementNode):
    def __init__(self, value = None, row: Optional[int] = None, **props) -> None:
        super().__init__(row=row, **props)
        self.value = value

    @property
    def childs(self) -> Tuple[AstNode]:
        return self.value,

    def semantic_check(self, scope: IdentScope):
        self.value.semantic_check(IdentScope(scope))
        func_scope = scope.curr_func
        if func_scope is None:
            self.semantic_error('Оператор return применим только к функции')
        # пытаемся понять, подходит ли возврат к возвращаемому значению функции
        self.value = type_convert(self.value, func_scope.func.type.return_type, self, 'возвращаемое значение')
        self.node_type = TypeDesc.VOID

    def __str__(self) -> str:
        return 'return'
    
EMPTY_STMT = StatementListNode()
EMPTY_IDENT = IdentDesc('', TypeDesc.VOID)
