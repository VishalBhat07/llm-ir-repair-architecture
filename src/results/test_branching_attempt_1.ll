define i32 @test_branching(i32 %0, i32 %1) {
entry:
  %2 = icmp sgt i32 %0, i32 %1
  %3 = zext i1 %2 to i32
  ret i32 %3
}