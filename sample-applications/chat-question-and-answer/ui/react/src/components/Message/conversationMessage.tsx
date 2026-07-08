// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { DateTime } from "luxon"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import style from "./conversationMessage.module.scss"
import conversationStyles from "../../styles/components/conversation.module.scss"

export interface ConversationMessageProps {
  message: string
  human: boolean
  date: number
  showBlinkingIndicator?: boolean
  responseTimeMs?: number
}

function splitReasoningAndAnswer(message: string): { reasoning: string; answer: string; hasReasoning: boolean } {
  const markerRegex = /(assistant\s*final|assistantfinal)\s*:?/i
  const markerMatch = markerRegex.exec(message)

  if (!markerMatch) {
    return { reasoning: "", answer: message, hasReasoning: false }
  }

  const reasoningRaw = message.slice(0, markerMatch.index)
  const answerRaw = message.slice(markerMatch.index + markerMatch[0].length)

  const reasoning = reasoningRaw.replace(/^\s*analysis\s*:?\s*/i, "").trim()
  const answer = answerRaw.trimStart()

  return {
    reasoning,
    answer,
    hasReasoning: reasoning.length > 0,
  }
}

export function ConversationMessage({
  human,
  message,
  date,
  showBlinkingIndicator = false,
  responseTimeMs,
}: ConversationMessageProps) {
  const dateFormat = () => {
    return DateTime.fromJSDate(new Date(date)).toLocaleString(DateTime.DATETIME_MED)
  }

  const normalizedMessage = message.replace(/\\n/g, "\n")
  const { reasoning, answer, hasReasoning } = splitReasoningAndAnswer(normalizedMessage)

  return (
    <div className={`${style.messageRow} ${human ? style.user : style.ai}`}>
      <div className={`${style.messageIcon} ${human ? style.userIcon : style.aiIcon}`}>
        {human ? "U" : "Q"}
      </div>

      <div className={style.messageContent}>
        <div className={`${style.bubble} ${human ? style.userBubble : style.aiBubble}`}>
          <div className={style.markdownContent}>
            {hasReasoning && !human ? (
              <>
                <div className={style.reasoningBlock}>
                  <div className={style.reasoningLabel}>Reasoning</div>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{reasoning}</ReactMarkdown>
                </div>

                <div className={style.answerSpacer} />

                <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
              </>
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizedMessage}</ReactMarkdown>
            )}

            {showBlinkingIndicator && (
              <span
                className={conversationStyles.blinkingIndicator}
                style={{ marginLeft: "4px", display: "inline-block", verticalAlign: "baseline" }}
              />
            )}
          </div>

          {showBlinkingIndicator && (
            <span
              className={conversationStyles.blinkingIndicator}
              style={{ marginLeft: "4px", display: "inline-block", verticalAlign: "baseline" }}
            />
          )}
        </div>

        <div className={style.messageDate}>{dateFormat()}</div>

        {!human && responseTimeMs !== undefined && (
          <div className={style.responseTime}>
            <span className={style.responseDot} />
            <span className={style.responseValue}>
              {(responseTimeMs / 1000).toFixed(2)}s
            </span>
            <span className={style.responseLabel}>response time</span>
          </div>
        )}
      </div>
    </div>
  )
}