import React from 'react'

export function SlackIcon({
  size = 20,
  className = '',
  style,
}: {
  size?: number
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <img
      src="/SLA-Slack-icon-RGB.svg"
      alt="Slack"
      width={size}
      height={size}
      className={className}
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        objectFit: 'contain',
        width: size,
        height: size,
        flexShrink: 0,
        ...style,
      }}
    />
  )
}

export function ClickUpIcon({
  size = 20,
  className = '',
  style,
}: {
  size?: number
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <img
      src="/clickup-logo.png"
      alt="ClickUp"
      width={size}
      height={size}
      className={className}
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        objectFit: 'contain',
        width: size,
        height: size,
        flexShrink: 0,
        ...style,
      }}
    />
  )
}
