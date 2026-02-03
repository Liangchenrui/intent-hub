#!/bin/sh
# 启动时确保 HuggingFace 缓存目录归 appuser 所有（命名卷挂载后常为 root）
if [ -n "$HF_HOME" ]; then
  chown -R appuser:appuser "$HF_HOME" 2>/dev/null || true
fi
exec gosu appuser "$@"
