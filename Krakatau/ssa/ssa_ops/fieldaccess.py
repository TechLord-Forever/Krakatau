from .base import BaseOp
from ...verifier.descriptors import parseFieldDescriptor
from ..ssa_types import verifierToSSAType, SSA_OBJECT, SSA_INT

from .. import objtypes, constraints, excepttypes
from ..constraints import IntConstraint, ObjectConstraint

# Empirically, Hotspot does enfore size restrictions on short fields
# Except that bool is still a byte
_short_constraints = {
        objtypes.ByteTT: IntConstraint.range(32, -128, 127),
        objtypes.CharTT: IntConstraint.range(32, 0, 65535),
        objtypes.ShortTT: IntConstraint.range(32, -32768, 32767),
        objtypes.IntTT: IntConstraint.bot(32)
    }
_short_constraints[objtypes.BoolTT] = _short_constraints[objtypes.ByteTT]
#Assume no linkage errors occur, so only exception that can be thrown is NPE
class FieldAccess(BaseOp):
    def __init__(self, parent, instr, info, args, monad):
        super(FieldAccess, self).__init__(parent, [monad]+args, makeException=('field' in instr[0]), makeMonad=True)

        self.instruction = instr
        self.target, self.name, self.desc = info

        dtype = None
        if 'get' in instr[0]:
            vtypes = parseFieldDescriptor(self.desc)
            stype = verifierToSSAType(vtypes[0])
            dtype = objtypes.verifierToSynthetic(vtypes[0]) #todo, find way to merge this with Invoke code?
            cat = len(vtypes)

            self.rval = parent.makeVariable(stype, origin=self)
            self.returned = [self.rval] + [None]*(cat-1)
        else:
            self.returned = []

        #just use a fixed constraint until we can do interprocedural analysis
        #output order is rval, exception, monad, defined by BaseOp.getOutputs
        env = parent.env
        self.mout = constraints.DUMMY
        self.eout = ObjectConstraint.fromTops(env, [excepttypes.NullPtr], [], nonnull=True)
        if self.rval is not None:
            if self.rval.type == SSA_OBJECT:
                supers, exact = objtypes.declTypeToActual(env, dtype)
                self.rout = ObjectConstraint.fromTops(env, supers, exact)
            elif self.rval.type == SSA_INT:
                self.rout = _short_constraints[dtype]
            else:
                self.rout = constraints.fromVariable(env, self.rval)

    def propagateConstraints(self, *incons):
        eout = None #no NPE
        if 'field' in self.instruction[0] and incons[1].null:
            eout = self.eout
            if incons[1].isConstNull():
                return None, eout, self.mout

        if self.rval is None:
            return None, eout, self.mout
        return self.rout, eout, self.mout
