from __future__ import annotations

from code_review_bot.diff import (
    anchor_finding,
    compact_diff,
    parse_diff,
    reviewable_source_files,
    source_change_counts,
    validate_suggestion,
)

DIFF = """diff --git a/src/main/java/com/acme/OrderController.java b/src/main/java/com/acme/OrderController.java
index 1111111..2222222 100644
--- a/src/main/java/com/acme/OrderController.java
+++ b/src/main/java/com/acme/OrderController.java
@@ -9,6 +9,10 @@ public class OrderController {
   }
 
   public Order get(String id, String callerId) {
     return orderRepository.findById(id);
   }
+
+  public String buildQuery(String id) {
+    return "SELECT * FROM orders WHERE id = " + id;
+  }
 }
diff --git a/src/main/python/app.py b/src/main/python/app.py
index 3333333..4444444 100644
--- a/src/main/python/app.py
+++ b/src/main/python/app.py
@@ -1,2 +1,3 @@
+import os
 def read(path):
     return open(path).read()
"""


def test_parse_anchors_and_suggestion() -> None:
    view = parse_diff(DIFF)
    assert "src/main/java/com/acme/OrderController.java" in view.anchors
    assert 11 in view.anchors["src/main/java/com/acme/OrderController.java"]
    assert 14 in view.anchors["src/main/java/com/acme/OrderController.java"]
    assert anchor_finding(view, "src/main/java/com/acme/OrderController.java", 11)
    assert not anchor_finding(view, "src/main/java/com/acme/OrderController.java", 99)
    ok, reason = validate_suggestion(
        view,
        "src/main/java/com/acme/OrderController.java",
        11,
        11,
        "return orderRepository.findByIdAndCustomerId(id, callerId);",
    )
    assert ok, reason
    bad, _ = validate_suggestion(
        view,
        "src/main/java/com/acme/OrderController.java",
        99,
        99,
        "x",
    )
    assert not bad


def test_source_selection_and_counts() -> None:
    view = parse_diff(DIFF)
    files = reviewable_source_files(view, 10)
    assert {f.path for f in files} == {
        "src/main/java/com/acme/OrderController.java",
        "src/main/python/app.py",
    }
    lines, count = source_change_counts(view, 10)
    assert lines > 0
    assert count == 2
    assert len(compact_diff(view, files, 1000)) <= 1000
