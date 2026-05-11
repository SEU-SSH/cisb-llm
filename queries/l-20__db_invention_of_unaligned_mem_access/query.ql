import cpp
import query

from RootCauseUnit var
where isTraversedAsArray(var) and assumesDefaultAlignmentShift()
select var, "CISB: Struct/union variable in linker section lacks explicit alignment, relying on compiler defaults."
