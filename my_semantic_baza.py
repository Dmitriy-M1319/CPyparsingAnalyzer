from typing import Any, Dict, Optional, Tuple
from enum import Enum
from binop import BinOp

# Встроенные в язык функции
BUILT_IN_OBJECTS = '''
    string input() { }
    void write(string s0) { }
    void writeline(string s1) { }
    int to_int(string s2) { }
    float to_float(string s3) { }
'''


class BaseType(Enum):
    """
    Возможные типы в программе
    """

    VOID = 'void'
    INT = 'int'
    FLOAT = 'float'
    STR = 'string'
    CHAR = 'char'

    def __str__(self):
        return self.value


VOID, INT, FLOAT, STR, CHAR = BaseType.VOID, BaseType.INT, BaseType.FLOAT, BaseType.STR, BaseType.CHAR


class TypeDesc:
    """
    Описание типа данных (просто объявление переменной или функция)
    """

    VOID: 'TypeDesc'
    INT: 'TypeDesc'
    FLOAT: 'TypeDesc'
    STR: 'TypeDesc'
    CHAR: 'TypeDesc'

    def __init__(self, base_type_: Optional[BaseType] = None,
                 return_type: Optional['TypeDesc'] = None, params: Optional[Tuple['TypeDesc']] = None) -> None:
        self.base_type = base_type_
        self.return_type = return_type
        self.params = params

    @property
    def func(self) -> bool:
        # Если существует тип возврата, то это функция
        return self.return_type is not None

    @property
    def is_simple(self) -> bool:
        # Если такого не существует, то это обычный тип данных (например, переменная)
        return not self.func

    def __eq__(self, other: 'TypeDesc'):
        """
        Сравнение типов данных(простых и функциональных)
        """
        if self.func != other.func: # если функциональные типы не равны
            return False
        if not self.func: # если данный тип не функция
            return self.base_type == other.base_type
        else:
            if self.return_type != other.return_type: # если не равны типы возврата
                return False
            if len(self.params) != len(other.params): # если не равно количество аргументов функций
                return False
            for i in range(len(self.params)):
                if self.params[i] != other.params[i]: # если типы параметров не совпадают
                    return False
            return True

    @staticmethod
    def from_base_type(base_type_: BaseType) -> 'TypeDesc':
        """
        Получить простой тип из базового типа
        """
        return getattr(TypeDesc, base_type_.name)

    @staticmethod
    def from_str(str_decl: str) -> 'TypeDesc':
        """
        Получить простой тип из строки
        """
        try:
            base_type_ = BaseType(str_decl)
            return TypeDesc.from_base_type(base_type_)
        except:
            raise SemanticException('Неизвестный тип ' + str_decl)

    def __str__(self) -> str:
        """
        Получить строку из объекта типа (либо просто тип, либо тип_возврата(параметр,...)
        """
        if not self.func:
            return str(self.base_type)
        else:
            res = str(self.return_type)
            res += ' ('
            for param in self.params:
                if res[-1] != '(':
                    res += ', '
                res += str(param)
            res += ')'
        return res


for base_type in BaseType: # для каждого объявления типа в TypeDesc устанавливаем сам объект TypeDesc
    setattr(TypeDesc, base_type.name, TypeDesc(base_type))


class ScopeType(Enum):
    """
    Возможные области видимости в программе 
    """
    GLOBAL = 'global'
    PARAM = 'param'
    LOCAL = 'local'

    def __str__(self):
        return self.value


class IdentDesc:
    """
    Описание идентификатора (переменная, функция)
    """

    # название, тип (TypeDesc), область видимости, в котором объявлена, индекс в стеке области
    def __init__(self, name: str, type_: TypeDesc, scope: ScopeType = ScopeType.GLOBAL, index: int = 0) -> None:
        self.name = name
        self.type = type_
        self.scope = scope
        self.index = index
        self.built_in = False # отвечает за то, встроенная функция в язык или нет

    def __str__(self) -> str:
        # тип , область , (built_in)?
        return str(self.type) + ' , ' + str(self.scope) + ', ' + 'built-in' if self.built_in else str(self.index)


class IdentScope:
    """
    Описание области видимости, в котором находится идентификатор
    """

    def __init__(self, parent: Optional['IdentScope'] = None) -> None:
        self.idents: Dict[str, IdentDesc] = {}  # стек объявлений в данной области
        self.func: Optional[IdentDesc] = None   # функция, которая является возможной областью видимости
        self.parent = parent                    # родительская область
        self.var_index = 0                      # индекс объявленных переменных
        self.param_index = 0                    # индекс каких-то параметров

    @property
    def is_global(self) -> bool:
        """Проверка на то, является ли данная область глобальной"""
        return self.parent is None

    @property
    def curr_global(self) -> 'IdentScope':
        """Вернуть глобальную область, в которой находится текущая область"""
        curr = self
        while curr.parent:
            curr = curr.parent
        return curr

    @property
    def curr_func(self) -> Optional['IdentScope']:
        """Вернуть функцию, в которой находится данная область"""
        curr = self
        while curr and not curr.func:
            curr = curr.parent
        return curr

    def add_ident(self, ident: IdentDesc) -> IdentDesc:
        """Добавить идентификатор в текущую область видимости"""
        func_scope = self.curr_func
        global_scope = self.curr_global

        # Если данный идентификатор не параметр функции
        # то делаем его локальным (если текущий скоуп - функция) или глобальным
        if ident.scope != ScopeType.PARAM:  
            ident.scope = ScopeType.LOCAL if func_scope else \
                ScopeType.GLOBAL

        # Пробуем найти возможное объявление с таким же именем
        old_ident = self.get_ident(ident.name)
        if old_ident: # если нашли, то вероятнее всего выкинет ошибку
            error = False
            if ident.scope == ScopeType.PARAM:
                if old_ident.scope == ScopeType.PARAM:
                    error = True
            elif ident.scope == ScopeType.LOCAL:
                if old_ident.scope != ScopeType.GLOBAL:
                    error = True
            else:
                error = True
            if error:
                raise SemanticException('Идентификатор '  + ident.name + ' уже объявлен')

        if not ident.type.func: # Если объявление не функция
            if ident.scope == ScopeType.PARAM:
                ident.index = func_scope.param_index # устанавливаем identу текущий индекс параметра функции
                func_scope.param_index += 1
            else:
                # Ставим скоуп функцию или глобальную
                ident_scope = func_scope if func_scope else global_scope 
                ident.index = ident_scope.var_index # ну и присвоение индекса
                ident_scope.var_index += 1

        # добавляем объявление в наш импровизированный стек
        self.idents[ident.name] = ident
        return ident

    def get_ident(self, name: str) -> Optional[IdentDesc]:
        """
        Получить объект идентификатора по его имени из стека
        """
        scope = self
        ident = None
        while scope:
            ident = scope.idents.get(name)
            if ident:
                break
            scope = scope.parent
        return ident


def prepare_global_scope() -> IdentScope:
    from my_parser import parse
    prog = parse(BUILT_IN_OBJECTS)
    scope = IdentScope()
    prog.semantic_check(scope)
    # prog.semantic_check(scope)
    for name, ident in scope.idents.items():
        ident.built_in = True
    scope.var_index = 0
    return scope


class SemanticException(Exception):
    """Класс для исключений во время семантического анализа
    """

    def __init__(self, message, row: int = None, **kwargs: Any) -> None:
        if row:
            message += " (строка: {})".format(row)
        self.message = message


TYPE_CONVERTIBILITY = {
    INT: (FLOAT, STR,),
    FLOAT: (STR,),
    CHAR: (STR,)
}


def can_type_convert_to(from_type: TypeDesc, to_type: TypeDesc) -> bool:
    """Проверка, может ли тип from_type приводиться к типу to_type"""
    if not from_type.is_simple or not to_type.is_simple: # Если данные типы - функции
        return False
    return from_type.base_type in TYPE_CONVERTIBILITY and to_type.base_type in TYPE_CONVERTIBILITY[to_type.base_type]


BIN_OP_TYPE_COMPATIBILITY = {
    BinOp.ADD: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT,
        (STR, STR): STR,
        (CHAR, CHAR): STR
    },
    BinOp.SUB: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.MUL: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.DIV: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.MOD: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },

    BinOp.GT: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },
    BinOp.LT: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },
    BinOp.GE: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },
    BinOp.LE: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },
    BinOp.EQ: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },
    BinOp.NE: {
        (INT, INT): INT,
        (FLOAT, FLOAT): INT,
        (STR, STR): INT,
        (CHAR, CHAR): INT,
    },

    BinOp.AND: {
        (INT, INT): INT,
    },
    BinOp.OR: {
        (INT, INT): INT,
    },
}
