{{- define "industrial-ai.name" -}}
industrial-ai
{{- end }}

{{- define "industrial-ai.labels" -}}
app.kubernetes.io/name: {{ include "industrial-ai.name" . }}
app.kubernetes.io/part-of: industrial-ai-platform
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

