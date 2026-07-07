"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Settings2, ShieldCheck, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { useAppStore } from "../../lib/store";
import type { RuntimeSettingsPatch } from "../../lib/types";

const presets = [
  {
    label: "Codex API / 中转站",
    providerName: "Codex API",
    homeUrl: "",
    baseUrl: "",
    model: "gpt-5.5",
    note: "OpenAI-compatible 中转服务",
  },
  {
    label: "OpenAI",
    providerName: "OpenAI",
    homeUrl: "https://openai.com",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-5.5",
    note: "",
  },
  {
    label: "DeepSeek",
    providerName: "DeepSeek",
    homeUrl: "https://www.deepseek.com",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-v4-pro",
    note: "",
  },
];

function statusText(configured: boolean) {
  return configured ? "已配置" : "未配置";
}

function statusClass(configured: boolean) {
  return configured
    ? "border-emerald-200 bg-emerald-50 text-pass"
    : "border-slate-200 bg-slate-50 text-slate-500";
}

export function SettingsDrawer() {
  const open = useAppStore((state) => state.settingsOpen);
  const setOpen = useAppStore((state) => state.setSettingsOpen);
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
  });
  const doctorQuery = useQuery({
    queryKey: ["doctor"],
    queryFn: api.getDoctor,
    enabled: open,
  });
  const settings = settingsQuery.data;
  const doctor = doctorQuery.data;
  const [providerName, setProviderName] = useState("Codex API");
  const [homeUrl, setHomeUrl] = useState("https://openai.com");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [openaiModel, setOpenaiModel] = useState("gpt-5.5");
  const [note, setNote] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [glmModel, setGlmModel] = useState("glm-4.6v");
  const [glmKey, setGlmKey] = useState("");

  useEffect(() => {
    if (!settings) {
      return;
    }
    setProviderName(settings.models.openai_compatible_provider_name);
    setHomeUrl(settings.models.openai_compatible_home_url);
    setBaseUrl(settings.models.openai_compatible_base_url);
    setOpenaiModel(settings.models.openai_compatible_model);
    setNote(settings.models.openai_compatible_note ?? "");
    setGlmModel(settings.models.glm_vision_model);
  }, [settings]);

  const mutation = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: () => {
      setOpenaiKey("");
      setGlmKey("");
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      queryClient.invalidateQueries({ queryKey: ["doctor"] });
    },
  });

  function applyPreset(index: number) {
    const preset = presets[index];
    setProviderName(preset.providerName);
    setHomeUrl(preset.homeUrl);
    setBaseUrl(preset.baseUrl);
    setOpenaiModel(preset.model);
    setNote(preset.note);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const patch: RuntimeSettingsPatch = {
      models: {
        text_llm_provider: "openai_compatible",
        openai_compatible_provider_name: providerName,
        openai_compatible_home_url: homeUrl,
        openai_compatible_base_url: baseUrl,
        openai_compatible_model: openaiModel,
        openai_compatible_note: note,
        browser_use_cloud_browser_enabled: false,
        glm_vision_model: glmModel,
      },
    };
    if (openaiKey) {
      patch.models.openai_compatible_api_key = openaiKey;
    }
    if (glmKey) {
      patch.models.glm_api_key = glmKey;
    }
    mutation.mutate(patch);
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="sp-overlay-in fixed inset-0 z-40 bg-ink/35 backdrop-blur-[2px]" />
        <Dialog.Content className="sp-drawer-in fixed bottom-2 right-2 top-2 z-50 flex w-full max-w-[560px] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-lift">
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
            <div className="flex items-center gap-3">
              <div
                className="grid h-9 w-9 place-items-center rounded-xl text-white"
                style={{ background: "var(--sp-gradient)" }}
              >
                <Settings2 size={18} />
              </div>
              <div>
                <Dialog.Title className="font-display text-base font-semibold">
                  系统设置
                </Dialog.Title>
                <Dialog.Description className="text-xs text-slate-500">
                  模型、密钥状态与执行参数
                </Dialog.Description>
              </div>
            </div>
            <Dialog.Close className="sp-icon-btn">
              <X size={18} />
            </Dialog.Close>
          </div>

          <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
              <section className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold">文本模型 API</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      使用 OpenAI-compatible / Codex API 格式接入文本模型。
                    </p>
                  </div>
                  <span className="sp-chip border-blue-100 bg-blue-50 text-run">
                    OpenAI-compatible
                  </span>
                </div>

                <div className="flex flex-wrap gap-2">
                  {presets.map((preset, index) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => applyPreset(index)}
                      className="rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-all duration-200 hover:border-blue-200 hover:bg-blue-50 hover:text-run"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <TextInput
                    label="供应商名称"
                    value={providerName}
                    onChange={setProviderName}
                    placeholder="例如：Clauddy"
                  />
                  <TextInput
                    label="备注"
                    value={note}
                    onChange={setNote}
                    placeholder="例如：公司专用账号"
                  />
                </div>
                <TextInput
                  label="官网链接"
                  value={homeUrl}
                  onChange={setHomeUrl}
                  placeholder="https://clauddy.com"
                />
                <SecretInput
                  label="API Key"
                  configured={
                    settings?.models.openai_compatible_api_key_configured ??
                    false
                  }
                  value={openaiKey}
                  onChange={setOpenaiKey}
                />
                <TextInput
                  label="API 请求地址"
                  value={baseUrl}
                  onChange={setBaseUrl}
                  placeholder="https://clauddy.com/v1"
                />
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-warn">
                  填写兼容 OpenAI Chat Completions 格式的服务端点根地址。
                </div>
                <TextInput
                  label="模型名称"
                  value={openaiModel}
                  onChange={setOpenaiModel}
                  placeholder="gpt-5.5"
                />
              </section>

              <section className="space-y-3">
                <h3 className="text-sm font-semibold">视觉验证</h3>
                <TextInput
                  label="GLM 视觉模型"
                  value={glmModel}
                  onChange={setGlmModel}
                />
                <SecretInput
                  label="GLM_API_KEY"
                  configured={settings?.models.glm_api_key_configured ?? false}
                  value={glmKey}
                  onChange={setGlmKey}
                />
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <label>
                    <span className="mb-1 block text-xs font-medium text-slate-500">
                      τ_high
                    </span>
                    <input
                      value="0.85"
                      readOnly
                      className="sp-input w-full bg-slate-50 font-mono text-slate-500"
                    />
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-slate-500">
                      τ_low
                    </span>
                    <input
                      value="0.60"
                      readOnly
                      className="sp-input w-full bg-slate-50 font-mono text-slate-500"
                    />
                  </label>
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Doctor 检查</h3>
                  <span
                    className={`sp-chip ${doctorStatusClass(doctor?.status)}`}
                  >
                    {doctorStatusText(doctor?.status, doctorQuery.isLoading)}
                  </span>
                </div>
                <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
                  {doctor ? (
                    Object.entries(doctor.checks).map(([name, check]) => (
                      <div
                        key={name}
                        className="grid grid-cols-[150px_72px_minmax(0,1fr)] items-center gap-3 px-3 py-2.5 text-xs odd:bg-slate-50/50"
                      >
                        <span className="font-mono text-slate-600">{name}</span>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-center ${doctorStatusClass(check.status)}`}
                        >
                          {doctorStatusText(check.status, false)}
                        </span>
                        <span
                          className="truncate text-slate-500"
                          title={check.detail}
                        >
                          {check.detail}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-3 text-sm text-slate-500">
                      <ShieldCheck size={16} />
                      {doctorQuery.isError ? "Doctor 接口暂不可用" : "等待检查结果"}
                    </div>
                  )}
                </div>
              </section>

              {settingsQuery.isError ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-fail">
                  设置接口暂不可用
                </p>
              ) : null}
              {mutation.isError ? (
                <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-fail">
                  保存失败，请检查后端设置接口
                </p>
              ) : null}
              {mutation.isSuccess ? (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-pass">
                  设置已写入 .env，后续新执行任务将使用新配置
                </p>
              ) : null}
            </div>

            <div className="flex shrink-0 items-center justify-between border-t border-line bg-slate-50/60 px-5 py-4">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <KeyRound size={15} />
                已保存密钥不会回显，留空不会覆盖
              </div>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="sp-btn-primary"
              >
                {mutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                保存设置
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function doctorStatusText(
  status: "ok" | "warning" | "error" | undefined,
  loading: boolean,
) {
  if (loading) {
    return "检查中";
  }
  if (status === "ok") {
    return "正常";
  }
  if (status === "warning") {
    return "警告";
  }
  if (status === "error") {
    return "错误";
  }
  return "未知";
}

function doctorStatusClass(status: "ok" | "warning" | "error" | undefined) {
  if (status === "ok") {
    return "border-emerald-200 bg-emerald-50 text-pass";
  }
  if (status === "warning") {
    return "border-amber-200 bg-amber-50 text-warn";
  }
  if (status === "error") {
    return "border-red-200 bg-red-50 text-fail";
  }
  return "border-slate-200 bg-slate-50 text-slate-500";
}

function TextInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-slate-500">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="sp-input w-full"
      />
    </label>
  );
}

function SecretInput({
  label,
  configured,
  value,
  onChange,
}: {
  label: string;
  configured: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 flex items-center justify-between text-xs font-medium text-slate-500">
        <span>{label}</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs ${statusClass(configured)}`}
        >
          {statusText(configured)}
        </span>
      </span>
      <input
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="填写新密钥"
        autoComplete="new-password"
        className="sp-input w-full"
      />
    </label>
  );
}
