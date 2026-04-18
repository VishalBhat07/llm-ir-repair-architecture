; ModuleID = 'main.c'
source_filename = "main.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128"
target triple = "arm64-apple-darwin"

@.str = private unnamed_addr constant [1 x i8] zeroinitializer, align 1

; Function Attrs: noinline nounwind optnone ssp uwtable
define i32 @main() #0 {
entry:
  %x = alloca i32, align 4
  store i32 0, ptr %x, align 4
  %0 = add nsw i32 10, 20
  store i32 %0, ptr %x, align 4
  %1 = load i32, ptr %x, align 4
  ret i32 %1
}

attributes #0 = { noinline nounwind optnone ssp uwtable "frame-pointer"="non-leaf" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" }

!llvm.module.flags = !{!0, !1, !2, !3, !4, !5}
!llvm.ident = !{!6}

!0 = !{i32 2, "Dwarf Version", i32 5}
!1 = !{i32 2, "Debug Info Version", i32 3}
!2 = !{i32 1, "wchar_size", i32 4}
!3 = !{i32 8, "PIC Level", i32 2}
!4 = !{i32 7, "uwtable", i32 1}
!5 = !{i32 7, "frame-pointer", i32 1}
!6 = !{!"clang version 18.1.5"}