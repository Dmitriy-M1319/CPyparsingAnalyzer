from enum import Enum


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
        return self.value