source_filename = "max.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128"
target triple = "arm64-apple-darwin"

define dso_local i32 @max(i32 noundef %0, i32 noundef %1) #0 {
entry:
  %2 = icmp sgt i32 %0, i32 %1
  br i1 %2, label %if.then, label %if.else

if.then:
  ret i32 %0

if.else:
  ret i32 %1
}

attributes #0 = { noinline nounwind optnone "frame-pointer"="non-leaf" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" }