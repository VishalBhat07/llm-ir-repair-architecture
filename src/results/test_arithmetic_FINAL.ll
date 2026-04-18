; ModuleID = 'test_arithmetic.ll'
source_filename = "test_arithmetic.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

; Function: add
; int add(int a, int b) { return a + b; }
define i32 @add(i32 %a, i32 %b) {
entry:
  %sum = add i32 %a, %b
  ret i32 %sum
}

; Function: main
; int main() { return add(1, 2); }
define i32 @main() {
entry:
  %call_add = call i32 @add(i32 1, i32 2)
  ret i32 %call_add
}

; Module flags metadata
!llvm.module.flags = !{!0, !1}
!llvm.ident = !{!2}

; Fix: Changed "Dwarf Version" to !"Dwarf Version" for correct metadata operand type.
!0 = !{i32 2, !"Dwarf Version", i32 5}
!1 = !{i32 2, !"Debug Info Version", i32 3}
!2 = !{!"clang version 15.0.0"}