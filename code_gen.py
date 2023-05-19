from typing import List, Union, Any

import visitor
from my_semantic_baza import CHAR, BaseType, TypeDesc, ScopeType, BinOp
from mel_ast import AstNode, DeclListNode, DeclNode, DeclTypeNode, LiteralNode, IdentNode, BinOpNode, TypeConvertNode, FuncCallNode, \
    ValueNode, FuncDeclNode, AssignNode, ReturnOpNode, IfOpNode, ForOpNode, StatementListNode, WhileOpNode

RUNTIME_CLASS_NAME = 'CompilerDemo.Runtime'
PROGRAM_CLASS_NAME = 'Program'

# Базовые типы данных для MSIL
MSIL_TYPE_NAMES = {
    BaseType.VOID: 'void',
    BaseType.INT: 'int32',
    BaseType.FLOAT: 'float64',
    BaseType.STR: 'string',
    BaseType.CHAR: 'uint16'
}


# Класс метки (типичная метка в ассемблере для переходов, обращений и тд)
class CodeLabel:
    def __init__(self):
        self.index = None

    def __str__(self):
        return f'IL_{self.index}'


# Строчка кода, помеченная меткой
class CodeLine:
    def __init__(self, code: str, *params: Union[str, CodeLabel], label: CodeLabel = None):
        self.code = code
        self.label = label
        self.params = params

    def __str__(self):
        line = ''
        if self.label:
            line += str(self.label) + ': '
        line += self.code
        for p in self.params:
            line += ' ' + str(p)
        return line


# Пока что найти все объявления переменных в указанной ноде
def find_vars_decls(node: AstNode) -> List[DeclNode]:
    vars_nodes: List[DeclNode] = []

    def find(node: AstNode) -> None:
        for n in (node.childs or []):
            if isinstance(n, DeclNode):
                vars_nodes.append(n)
            else:
                find(n)

    find(node)
    return vars_nodes


# Сам класс кодогенерации
class CodeGenerator:
    def __init__(self):
        self.code_lines: List[CodeLine] = []
        self.indent = ''

    def add(self, code: str, *params: Union[str, int, CodeLabel], label: CodeLabel = None):
        # Тут происходит какая то магия с добавлением строчек кода
        if len(code) > 0 and code[-1] == '}':
            self.indent = self.indent[2:]
        self.code_lines.append(CodeLine(self.indent + str(code), *params, label=label))
        if len(code) > 0 and code[-1] == '{':
            self.indent = self.indent + '  '

    @property
    def code(self) -> [str, ...]:
        index = 0
        # Берем построчно весь код
        for cl in self.code_lines:
            line = cl.code
            # Раскидываем индексы для всех меток 
            if cl.label:
                cl.label.index = index
                index += 1
        # Делаем пустой список строк
        code: List[str] = []
        # и после того, как раскидали индексы меток, собираем все в одну кучу
        for cl in self.code_lines:
            code.append(str(cl))
        return code

    # Добавление директивы начала сборки и указания класса, где будет находиться наш код
    def start(self) -> None:
        self.add('.assembly program')
        self.add('{')
        self.add('}')
        self.add('.class public ' + PROGRAM_CLASS_NAME)
        self.add('{')

    # Добавить завершение сборки
    def end(self) -> None:
        self.add('}')

    @visitor.on('AstNode')
    def msil_gen(self, AstNode):
        """
        Нужен для работы модуля visitor (инициализации диспетчера)
        """
        pass

    # Генерация кода для литералов
    @visitor.when(LiteralNode)
    def msil_gen(self, node: LiteralNode) -> None:
        if node.node_type.base_type == BaseType.INT:
            self.add('ldc.i4', node.value)
        elif node.node_type.base_type == BaseType.CHAR:
            self.add('ldc.i2', ord(node.value))
        elif node.node_type.base_type == BaseType.FLOAT:
            self.add('ldc.r8', str(node.value))
        elif node.node_type.base_type == BaseType.STR:
            self.add(f'ldstr "{node.value}"')
        else:
            pass

    # Генерация кода для идентификаторов
    @visitor.when(IdentNode)
    def msil_gen(self, node: IdentNode) -> None:
        # Если идентификатор находится в локальной области видимости, то помечаем его инструкцией ldloc: загружает в стек локальную переменную 
        if node.node_ident.scope == ScopeType.LOCAL:
            self.add('ldloc', node.node_ident.index)
        # Для параметров функций инструкция ldarg загружает аргумент в стек
        elif node.node_ident.scope == ScopeType.PARAM:
            self.add('ldarg', node.node_ident.index)
        # Так как MSIL компилирует C# код, то все, что объявлено как глобально, должно быть статическим полем класса Program
        elif node.node_ident.scope == ScopeType.GLOBAL:
            self.add(f'ldsfld {MSIL_TYPE_NAMES[node.node_ident.type.base_type]} {PROGRAM_CLASS_NAME}::_gv{node.node_ident.index}')

    # Генерация кода для операции присваивания
    @visitor.when(AssignNode)
    def msil_gen(self, node: AssignNode) -> None:
        # Добавляем инструкцию для аргумента присваивания
        self.msil_gen(node.val)
        var = node.var
        # А теперь то значение, которое мы пихнули в стек, выпихиваем оттуда и сохраняем в память согласно области видимости
        if var.node_ident.scope == ScopeType.LOCAL:
            self.add('stloc', var.node_ident.index)
        elif var.node_ident.scope == ScopeType.PARAM:
            self.add('starg', var.node_ident.index)
        elif var.node_ident.scope == ScopeType.GLOBAL:
            self.add(f'stsfld {MSIL_TYPE_NAMES[var.node_ident.type.base_type]} Program::_gv{var.node_ident.index}')

    # Генерация кода для переменной
    # Тут тупо если для переменной заготовлено значение, то генерируем инструкции присваивания
    @visitor.when(DeclNode)
    def msil_gen(self, node: DeclNode) -> None:
        if node.init_value != None:
            self.msil_gen(node.init_value)
            var = node.ident
            # А теперь то значение, которое мы пихнули в стек, выпихиваем оттуда и сохраняем в память согласно области видимости
            if var.node_ident.scope == ScopeType.LOCAL:
                self.add('stloc', var.node_ident.index)
            elif var.node_ident.scope == ScopeType.PARAM:
                self.add('starg', var.node_ident.index)
            elif var.node_ident.scope == ScopeType.GLOBAL:
                self.add(f'stsfld {MSIL_TYPE_NAMES[var.node_ident.type.base_type]} Program::_gv{var.node_ident.index}')

    # Оп, генерация кода для бинарной операции
    @visitor.when(BinOpNode)
    def msil_gen(self, node: BinOpNode) -> None:
        # Генерируем инструкции для аргументов нашего действия (укладываем в стек)
        self.msil_gen(node.arg1)
        self.msil_gen(node.arg1)
        # Итак, если операция - это неравенство
        if node.op == BinOp.NE:
            if node.arg1.node_type == TypeDesc.STR:
                self.add('call bool [mscorlib]System.String::op_Inequality(string, string)')
            else:
                self.add('ceq')
                self.add('ldc.i4.0')
                self.add('ceq')
        if node.op == BinOp.EQ:
            if node.arg1.node_type == TypeDesc.STR:
                self.add('call bool [mscorlib]System.String::op_Equality(string, string)')
            else:
                self.add('ceq')
        # сравнения на строгое больше/меньше там, для строк снова используется ход сравнения с 0
        elif node.op == BinOp.GT:
            if node.arg1.node_type == TypeDesc.STR:
                self.add(f'call {MSIL_TYPE_NAMES[BaseType.INT]} class {RUNTIME_CLASS_NAME}::compare({MSIL_TYPE_NAMES[BaseType.STR]}, {MSIL_TYPE_NAMES[BaseType.STR]})')
                self.add('ldc.i4.0')
                self.add('cgt')
            else:
                self.add('cgt')
        elif node.op == BinOp.LT:
            if node.arg1.node_type == TypeDesc.STR:
                self.add(f'call {MSIL_TYPE_NAMES[BaseType.INT]} class {RUNTIME_CLASS_NAME}::compare({MSIL_TYPE_NAMES[BaseType.STR]}, {MSIL_TYPE_NAMES[BaseType.STR]})')
                self.add('ldc.i4.0')
                self.add('clt')
            else:
                self.add('clt')
        elif node.op == BinOp.GE:
            if node.arg1.node_type == TypeDesc.STR:
                self.add(f'call {MSIL_TYPE_NAMES[BaseType.INT]} class {RUNTIME_CLASS_NAME}::compare({MSIL_TYPE_NAMES[BaseType.STR]}, {MSIL_TYPE_NAMES[BaseType.STR]})')
                self.add('ldc.i4', '-1')
                self.add('cgt')
            else:
                self.add('clt')
                self.add('ldc.i4.0')
                self.add('ceq')
        elif node.op == BinOp.LE:
            if node.arg1.node_type == TypeDesc.STR:
                self.add(f'call {MSIL_TYPE_NAMES[BaseType.INT]} class {RUNTIME_CLASS_NAME}::compare({MSIL_TYPE_NAMES[BaseType.STR]}, {MSIL_TYPE_NAMES[BaseType.STR]})')
                self.add('ldc.i4.1')
                self.add('clt')
            else:
                self.add('cgt')
                self.add('ldc.i4.0')
                self.add('ceq')
        elif node.op == BinOp.ADD:
            if node.arg1.node_type == TypeDesc.STR or node.arg1.node_type == TypeDesc.CHAR:
                self.add(f'call {MSIL_TYPE_NAMES[BaseType.STR]} class {RUNTIME_CLASS_NAME}::concat({MSIL_TYPE_NAMES[BaseType.STR]}, {MSIL_TYPE_NAMES[BaseType.STR]})')
            else:
                self.add('add')
        # Для остального используется метод добавления add, потому что это операции, которые делают преобразования с числами
        elif node.op == BinOp.SUB:
            self.add('sub')
        elif node.op == BinOp.MUL:
            self.add('mul')
        elif node.op == BinOp.DIV:
            self.add('div')
        elif node.op == BinOp.MOD:
            self.add('rem')
        elif node.op == BinOp.AND:
            self.add('and')
        elif node.op == BinOp.OR:
            self.add('or')
        else:
            pass

    # Генерация кода для преобразования типов
    @visitor.when(TypeConvertNode)
    def msil_gen(self, node: TypeConvertNode) -> None:
        # Сначала в стек надо пихнуть надо выражение, которое будет преобразовано
        node.expr.msil_gen(self)
        # Кто то забыл слово надо :)
        # часто встречаемые варианты будет реализовывать в коде, а не через класс Runtime
        
        # определяем конвертирование целочисленного типа в плавующую точку
        if node.node_type.base_type == BaseType.FLOAT and node.expr.node_type.base_type == BaseType.INT:
            self.add('conv.r8')
        elif node.node_type.base_type == BaseType.CHAR and node.expr.node_type.base_type == BaseType.INT:
            self.add('conv.i2')
        # тут тупо приводим число в булевскому типу, как в Си (если не 0, то тру, иначе не тру)
        elif node.expr.node_type.base_type == BaseType.INT:
            self.add('ldc.i4.0')
            self.add('ceq')
            self.add('ldc.i4.0')
            self.add('ceq')
        else:
            # используется фича преобразования из стандартной либы
            cmd = f'call {MSIL_TYPE_NAMES[node.node_type.base_type]} class {RUNTIME_CLASS_NAME}::convert({MSIL_TYPE_NAMES[node.expr.node_type.base_type]})'
            self.add(cmd)

    # Генерация кода для вызова функции
    @visitor.when(FuncCallNode)
    def msil_gen(self, node: FuncCallNode) -> None:
        # Сначала надо сгенерить код и поместить все параметры в стек
        for param in node.params:
            param.msil_gen(self)

        # Потом надо определиться с названием вызова функции и расставления параметров
        class_name = RUNTIME_CLASS_NAME if node.name.node_ident.built_in else PROGRAM_CLASS_NAME
        param_types = ', '.join(MSIL_TYPE_NAMES[param.node_type.base_type] for param in node.params)
        # Просто инструкция вызова функции
        cmd = f'call {MSIL_TYPE_NAMES[node.node_type.base_type]} class {class_name}::{node.name.name}({param_types})'
        self.add(cmd)

    # Генерация кода для оператора возврата
    @visitor.when(ReturnOpNode)
    def msil_gen(self, node: ReturnOpNode) -> None:
        # тут ничего сверхъестественного: сначала помещаем то, что мы возвращаем, в стек, 
        # а потом делаем return через местную инструкцию ret
        self.msil_gen(node.value)
        self.add('ret')

    # Генерация кода для if (вот он, условный переход)
    @visitor.when(IfOpNode)
    def msil_gen(self, node: IfOpNode) -> None:
        # создаем метки для блока else и для обозначения конца блока if
        else_label = CodeLabel()
        end_label = CodeLabel()

        # генерим условие перехода (вписываем результат вычисления условия в стек)
        self.msil_gen(node.cond)
        # инструкция, с помощью которой если if не сработал, нас перебрасывает на метку с else
        self.add('brfalse', else_label)
        # генерим тело if
        self.msil_gen(node.thenStmts)
        # здесь выполняется тупо безусловный переход в конец if
        self.add('br', end_label)
        # ставим метку конца if
        self.add('', label=else_label)
        if node.elseStmts:
            # если у нас присутствует блок else, то генерируем и его
            self.msil_gen(node.elseStmts)
        self.add('', label=end_label)

    # Генерация кода для цикла while (похожа на if)
    @visitor.when(WhileOpNode)
    def msil_gen(self, node: WhileOpNode) -> None:
        start_label = CodeLabel()
        end_label = CodeLabel()

        self.add('', label=start_label)
        self.msil_gen(node.cond)
        end_label = CodeLabel()
        self.add('brfalse', end_label)
        self.msil_gen(node.stmts)
        self.add('br', start_label)
        self.add('', label=end_label)

    # Генерация кода для for
    @visitor.when(ForOpNode)
    def msil_gen(self, node: ForOpNode) -> None:
        start_label = CodeLabel()
        end_label = CodeLabel()

        # генерируем инициализирующий блок
        self.msil_gen(node.decl)
        self.add('', label=start_label)
        # потом создаем условие, согласно которому будет выполняться цикл или нет
        self.msil_gen(node.cond)
        self.add('brfalse', end_label)
        # генерируем тело цикла
        self.msil_gen(node.body)
        # ну и инструкции при продвижении цикла вперед
        self.msil_gen(node.stmt)
        self.add('br', start_label)
        self.add('', label=end_label)

    # Генерация кода описания функции
    @visitor.when(FuncDeclNode)
    def msil_gen(self, func: FuncDeclNode) -> None:

        # в результате генерации сигнатуры должна получиться такая басня
        # .method public static int32 Add(int32 a, int32 b) cil managed (как пример)

        # итак, тут мы приводим параметры в нужный нам вид
        params = ''
        for p in func.params.params:
            if len(params) > 0:
                params += ', '
            params += f'{MSIL_TYPE_NAMES[p.decl_type.node_type.base_type]} {str(p.ident.name)}'
        self.add(f'.method public static {MSIL_TYPE_NAMES[func.func_type.node_type.base_type]} {func.name}({params}) cil managed')
        self.add('{')

        # Тут мы ищем все локальные переменные и заносим их в специальный блок (ну тупо как в Паскале или первые стандарты написания кода в Си)
        # чтобы получилась такая дичь     .locals init (int32 result, int32 i)   (как пример)
        local_vars_decls = find_vars_decls(func)
        decl = '.locals init ('
        count = 0
        for var in local_vars_decls:
            if var.ident.node_ident.scope == ScopeType.LOCAL:
                    if count > 0:
                        decl += ', '
                    decl += f'{MSIL_TYPE_NAMES[var.node_type.base_type]} _v{var.node_ident.index}'
                    count += 1
        decl += ')'
        if count > 0:
            self.add(decl)

        # и осталось сгенерировать набор инструкция тела функции
        self.msil_gen(func.body)

        # при необходимости добавим ret
        if not (isinstance(func.body, ReturnOpNode) or
                len(func.body.childs) > 0 and isinstance(func.body.childs[-1], ReturnOpNode)):
            self.add('ret')
        self.add('}')

    # Генерация списка выражений
    @visitor.when(StatementListNode)
    def msil_gen(self, node: StatementListNode) -> None:
        # ну здесь тупо проходимся по всему списку и делаем с каждым выражением грязь
        for stmt in node.exprs:
            self.msil_gen(stmt)

    # Самая вишенка: генерация всей программы
    def msil_gen_program(self, prog: StatementListNode):
        # ставим метку начала
        self.start()
        # находим все глобальные переменные и делаем их статическими полями базового класса Program
        global_vars_decls = find_vars_decls(prog)
        for var in global_vars_decls:
            if var.ident.node_ident.scope == ScopeType.GLOBAL:
                self.add(f'.field public static {MSIL_TYPE_NAMES[var.node_type.base_type]} _gv{var.ident.node_ident.index}')
        # Тут генерируем все описания функций
        for stmt in prog.exprs:
            if isinstance(stmt, FuncDeclNode):
                self.msil_gen(stmt)

        # главное: точка входа в программу
        self.add('')
        self.add('.method public static void Main()')
        self.add('{')
        self.add('.entrypoint')

        # здесь генерируем код функции main
        for stmt in prog.childs:
            # а здесь уже все объявления функций выкидываем, никому не нужны функции в функции
            if not isinstance(stmt, FuncDeclNode):
                self.msil_gen(stmt)

        # т.к. "глобальный" код будет функцией, обязательно надо добавить ret
        self.add('ret')

        self.add('}')
        self.end()
