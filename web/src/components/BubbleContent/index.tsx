import useIntlConfig from "@/hooks/useIntlConfig";
import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import gfm from "remark-gfm";
import { Spin } from "antd";
import styles from "./index.less";
import { MESSAGE_TYPE } from "@/constants";
import { getTimeDifference } from "@/utils/getTimeDifference";
import GraphMessage from "@/components/GraphMessage";

interface BubbleContentProps {
  status?: string;
  content: string;
  message: API.ChatVO;   // 用于承载最终阶段的附加消息（含图谱）
  isLast: boolean;
  onRecoverSession: () => void;
}

const BubbleContent: React.FC<BubbleContentProps> = ({
  status,
  content,
  message,
  isLast,
  onRecoverSession,
}) => {
  const { formatMessage } = useIntlConfig();

  // 运行中显示“已用时 mm:ss”
  const startRef = useRef<number>(Date.now());
  const [elapsedMs, setElapsedMs] = useState(0);

  // 状态切到“创建/运行”时重置起点，并启动计时器；其他状态时停止
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    if (status === MESSAGE_TYPE.CREATED || status === MESSAGE_TYPE.RUNNING) {
      startRef.current = Date.now();
      setElapsedMs(0);
      timer = setInterval(() => setElapsedMs(Date.now() - startRef.current), 1000);
    } else {
      setElapsedMs(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [status]);

  const timeText = useMemo(() => {
    if (elapsedMs <= 0) return "";
    const { minutes, seconds } = getTimeDifference(elapsedMs);
    const mm = String(minutes).padStart(2, "0");
    const ss = String(seconds).padStart(2, "0");
    return `${mm}:${ss}`;
  }, [elapsedMs]);

  const isRunning =
    status === MESSAGE_TYPE.CREATED || status === MESSAGE_TYPE.RUNNING;
  const isDone =
    status === MESSAGE_TYPE.FINISHED || status === MESSAGE_TYPE.FAILED;

  const attached = Array.isArray(message?.attached_messages)
    ? message.attached_messages
    : [];

  return (
    <div className={styles["bubble-content"]}>
      {/* 运行中：只显示等待特效与计时 */}
      {isRunning && (
        <div className={styles.runningBar}>
          <Spin size="small" />
          <span className={styles.runningTime}>{timeText}</span>
        </div>
      )}

      {/* 完成/失败：显示最终 Markdown 回复 + GraphMessage（知识图谱等附加内容） */}
      {isDone && (
        <div className={styles["bubble-content-message"]}>
          {content ? (
            <ReactMarkdown remarkPlugins={[gfm]}>{content}</ReactMarkdown>
          ) : null}

          {attached.length > 0 && (
            <div className={styles.graphList}>
              {attached.map((m: any) => (
                <GraphMessage key={m?.id ?? m?.jobId} message={m} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* 停止：保留恢复入口 */}
      {isLast && status === MESSAGE_TYPE.STOPPED ? (
        <div className={styles["bubble-content-footer"]}>
          <div
            className={styles["bubble-content-footer-recover"]}
            onClick={onRecoverSession}
          >
            <i
              className="iconfont icon-Chat2graphjixusikao"
              style={{ fontSize: 24 }}
            />
            <span>{formatMessage("home.recover")}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default BubbleContent;
