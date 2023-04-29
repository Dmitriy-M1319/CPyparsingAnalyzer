from typing import List, Optional

import visitor
from my_semantic_baza import TypeDesc, ScopeType, SemanticException, BIN_OP_TYPE_COMPATIBILITY, TYPE_CONVERTIBILITY
from mel_ast import *
from my_parser import parse


# Встроенные в язык функции
BUILT_IN_OBJECTS = '''
    string input() { }
    void write(string s0) { }
    void writeline(string s0) { }
    int to_int(string s0) { }
    float to_float(string s0) { }
'''


def type_convert(expr: ValueNode, type_: TypeDesc, except_node: Optional[AstNode] = None, comment: Optional[str] = None) -> ValueNode:
    """Метод преобразования ExprNode узла AST-дерева к другому типу
    :param expr: узел AST-дерева
    :param type_: требуемый тип
    :param except_node: узел, о которого будет исключение
    :param comment: комментарий
    :return: узел AST-дерева c операцией преобразования
    """

    if expr.node_type is None:
        except_node.semantic_error('Тип выражения не определен')
    if expr.node_type == type_: # если типы одни и те же
        return expr
    # если типы простые и все четко конвертируется
    if expr.node_type.is_simple and type_.is_simple and \
            expr.node_type.base_type in TYPE_CONVERTIBILITY and type_.base_type in TYPE_CONVERTIBILITY[expr.node_type.base_type]:
        return TypeConvertNode(expr, type_)
    else:
        (except_node if except_node else expr).semantic_error('Тип {0}{2} не конвертируется в {1}'.format(
            expr.node_type, type_, ' ({})'.format(comment) if comment else ''
        ))


class SemanticChecker:
    @visitor.on('AstNode')
    def semantic_check(self, AstNode): # базовый метод проверки семантики
        pass

    @visitor.when(LiteralNode) # если мы посетили литерал
    def semantic_check(self, node: LiteralNode, scope: IdentScope):
        # пытаемся определить тип литерала
        if isinstance(node.value, int):
            node.node_type = TypeDesc.INT
        elif isinstance(node.value, float):
            node.node_type = TypeDesc.FLOAT
        elif isinstance(node.value, str):
            if node.value[0] == '"':
                node.node_type = TypeDesc.STR
            else:
                node.node_type = TypeDesc.CHAR
        else:
            node.semantic_error('Неизвестный тип ' + str(type(node.value)) + ' для ' + str(node.value))

    @visitor.when(IdentNode) # если мы посетили идентификатор
    def semantic_check(self, node: IdentNode, scope: IdentScope):
        ident = scope.get_ident(node.name) # ищем данное объявление в местной области видимости
        if ident is None:
            node.semantic_error('Идентификатор' + str(node.name) + 'не найден')
        node.node_type = ident.type # в качестве типа узла присваиваем тип идентификатора
        node.node_ident = ident     # и сам идентификатор

    @visitor.when(DeclTypeNode) # посетили объявление типа
    def semantic_check(self, node: DeclTypeNode, scope: IdentScope):
        if node.type is None:
            node.semantic_error('Неизвестный ' + str(node.name) + ' тип')

    @visitor.when(BinOpNode) # посетили узел бинарной операции
    def semantic_check(self, node: BinOpNode, scope: IdentScope):
        # проверяем каждый аргумент
        node.arg1.semantic_check(self, scope)
        node.arg2.semantic_check(self, scope)

        if node.arg1.node_type.is_simple or node.arg2.node_type.is_simple: # если один из аргументов представляет собой простой тип
            compatibility = BIN_OP_TYPE_COMPATIBILITY[node.op] # находим типы, которые между собой могут взаимодействовать
            args_types = (node.arg1.node_type.base_type, node.arg2.node_type.base_type)
            if args_types in compatibility:
                node.node_type = TypeDesc.from_base_type(compatibility[args_types]) # если с типами все ок, устанавливаем итоговый тип выражения
                return

            if node.arg2.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg2_type in TYPE_CONVERTIBILITY[node.arg2.node_type.base_type]:
                    args_types = (node.arg1.node_type.base_type, arg2_type)
                    if args_types in compatibility:
                        node.arg2 = type_convert(node.arg2, TypeDesc.from_base_type(arg2_type))
                        node.node_type = TypeDesc.from_base_type(compatibility[args_types])
                        return
            if node.arg1.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg1_type in TYPE_CONVERTIBILITY[node.arg1.node_type.base_type]:
                    args_types = (arg1_type, node.arg2.node_type.base_type)
                    if args_types in compatibility:
                        node.arg1 = type_convert(node.arg1, TypeDesc.from_base_type(arg1_type))
                        node.node_type = TypeDesc.from_base_type(compatibility[args_types])
                        return

        node.semantic_error("Оператор {} не применим к типам ({}, {})".format(
            node.op, node.arg1.node_type, node.arg2.node_type
        ))

    @visitor.when(FuncCallNode) # посещаем вызов функции
    def semantic_check(self, node: FuncCallNode, scope: IdentScope):
        func = scope.get_ident(node.name.name) # получаем объект идентификатора функции
        if func is None:
            node.semantic_error('Функция {} не найдена'.format(node.name.name))
        if not func.type.func: # если данный идентификатор не функция 
            node.semantic_error('Идентификатор {} не является функцией'.format(func.name))
        if len(func.func_type.params) != len(node.params):
            node.semantic_error('Кол-во аргументов {} не совпадает (ожидалось {}, передано {})'.format(
                func.name, len(func.func_type.params), len(node.params)
            ))
        params = []
        error = False
        decl_params_str = fact_params_str = ''
        for i in range(len(node.params)):
            param: ValueNode = node.params[i] # вытаскиваем какое то rvalue значение или expr
            param.semantic_check(self, scope)
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
            node.semantic_error('Фактические типы ({1}) аргументов функции {0} не совпадают с формальными ({2})\
                                            и не приводимы'.format(
                func.name, fact_params_str, decl_params_str
            ))
        else:
            node.params = tuple(params)
            node.name.node_type = func.type
            node.name.node_ident = func
            node.node_type = func.type.return_type

    @visitor.when(AssignNode) # посещаем присваивание
    def semantic_check(self, node: AssignNode, scope: IdentScope):
        node.var.semantic_check(self, scope)
        node.val.semantic_check(self, scope)
        node.val = type_convert(node.val, node.var.node_type, node, 'присваиваемое значение')
        node.node_type = node.var.node_type

    @visitor.when(DeclNode)
    def semantic_check(self, node: DeclNode, scope: IdentScope):
        node.decl_type.semantic_check(self, scope)
        try:
            scope.add_ident(IdentDesc(node.ident, node.decl_type.type))
        except SemanticException as e:
            node.semantic_error(e.message) 
        node.node_type = TypeDesc.VOID # вот это не очень понятна

    @visitor.when(ReturnOpNode) # посещаем узел возврата
    def semantic_check(self, node: ReturnOpNode, scope: IdentScope):
        node.value.semantic_check(self, IdentScope(scope))
        func_scope = scope.curr_func
        if func_scope is None:
            node.semantic_error('Оператор return применим только к функции')
        # пытаемся понять, подходит ли возврат к возвращаемому значению функции
        node.value = type_convert(node.value, func_scope.func.func_type.return_type, node, 'возвращаемое значение')
        node.node_type = TypeDesc.VOID

    @visitor.when(IfOpNode)
    def semantic_check(self, node: IfOpNode, scope: IdentScope):
        node.cond.semantic_check(self, scope)
        node.cond = type_convert(node.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        node.thenStmts.semantic_check(self, IdentScope(scope))
        if node.elseStmts:
            node.elseStmts.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(WhileOpNode)
    def semantic_check(self, node: WhileOpNode, scope: IdentScope):
        node.cond.semantic_check(self, scope)
        node.cond = type_convert(node.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        node.stmts.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(ForOpNode)
    def semantic_check(self, node: ForOpNode, scope: IdentScope):
        scope = IdentScope(scope)
        node.decl.semantic_check(self, scope) # проверяем объявления
        if node.cond == EMPTY_STMT:
            node.cond = LiteralNode('1')
        node.cond.semantic_check(self, scope) # проверяем условие
        node.cond = type_convert(node.cond, TypeDesc.INT, None, 'условие') # приводим к int, так как у нас в обычном С нет булевского типа
        node.stmt.semantic_check(self, scope) # проверяем выражения в заголовке цикла
        node.body.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(DeclListNode)
    def semantic_check(self, node: DeclListNode, scope: IdentScope):
        for param in node.params:
            param.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(FuncDeclNode) # посещаем объявление функции
    def semantic_check(self, node: FuncDeclNode, scope: IdentScope):
        if scope.curr_func:
            node.semantic_error("Объявление функции ({}) внутри другой функции не поддерживается".format(node.name.name))
        parent_scope = scope
        node.func_type.semantic_check(self, scope) # проверяем возвращаемый тип
        scope = IdentScope(scope)

        scope.func = EMPTY_IDENT # делаем так, что текущая функция не входит в другую функцию
        params: List[TypeDesc] = [] # начинаем перебирать параметры
        for param in node.params.params:
            param.semantic_check(self, scope)
            params.append(param.decl_type.type)

        type_ = TypeDesc(None, node.func_type.type, tuple(params))
        func_ident = IdentDesc(node.name.name, type_)
        scope.func = func_ident
        node.name.node_type = type_
        try:
            node.name.node_ident = parent_scope.curr_global.add_ident(func_ident)
        except SemanticException as e:
            node.name.semantic_error("Повторное объявление функции {}".format(node.name.name))
        node.body.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(StatementListNode)
    def semantic_check(self, node: StatementListNode, scope: IdentScope):
        if not node.program:
            scope = IdentScope(scope)
        for stmt in node.exprs:
            stmt.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID


def prepare_global_scope() -> IdentScope:
    prog = parse(BUILT_IN_OBJECTS)
    checker = SemanticChecker()
    scope = IdentScope()
    checker.semantic_check(prog, scope)
    # prog.semantic_check(scope)
    for name, ident in scope.idents.items():
        ident.built_in = True
    scope.var_index = 0
    return scope
