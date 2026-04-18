; ModuleID = 'fixed_ir_module'
source_filename = "fixed_ir.ll"

define i1 @test_branching_fixed(i32 %0, i32 %1) {
entry:
  %2 = icmp sgt i32 %0, i32 %1
  ret i1 %2
}