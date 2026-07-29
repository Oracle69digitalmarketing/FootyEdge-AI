import React, { useCallback, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Divider,
  Flex,
  Group,
  Menu,
  Modal,
  ScrollArea,
  SegmentedControl,
  Stack,
  Switch,
  Text,
} from "@mantine/core";
import { useTranslation } from "react-i18next";
import AutorenewIcon from "@mui/icons-material/Autorenew";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import FileDownloadIcon from "@mui/icons-material/FileDownloadOutlined";

import {
  PdfTextEditorViewData,
  TextGroup,
} from "@app/tools/pdfTextEditor/pdfTextEditorTypes";
import { pageDimensions } from "@app/tools/pdfTextEditor/pdfTextEditorUtils";
import FontStatusPanel from "@app/components/tools/pdfTextEditor/FontStatusPanel";
import ToolStep from "@app/components/tools/shared/ToolStep";
import { usePdfTextEditorTips } from "@app/components/tooltips/usePdfTextEditorTips";
import { Tooltip } from "@app/components/shared/Tooltip";
import LocalIcon from "@app/components/shared/LocalIcon";

type GroupingMode = "auto" | "paragraph" | "singleLine";

interface PdfTextEditorSidebarProps {
  data: PdfTextEditorViewData;
}

// Analyze page content to determine if it's paragraph-heavy
const analyzePageContentType = (
  groups: TextGroup[],
  pageWidth: number,
): boolean => {
  if (groups.length < 3) {
    return false;
  }

  const widths = groups.map((g) => Math.max(g.bounds.right - g.bounds.left, 1));
  const avgWidth = widths.reduce((sum, w) => sum + w, 0) / widths.length;
  const stdDev = Math.sqrt(
    widths.reduce((sum, w) => sum + Math.pow(w - avgWidth, 2), 0) /
      widths.length,
  );
  const coefficientOfVariation = avgWidth > 0 ? stdDev / avgWidth : 0;
  const fullWidthRatio =
    widths.filter((w) => w > pageWidth * 0.65).length / widths.length;

  const criterion1 = groups.length >= 3;
  const criterion2 = avgWidth > pageWidth * 0.3;
  const criterion3 = coefficientOfVariation > 0.5 || fullWidthRatio > 0.6;

  return criterion1 && criterion2 && criterion3;
};

import SecurityIcon from "@mui/icons-material/Security";

// ... (existing code)

const PdfTextEditorSidebar = ({ data }: PdfTextEditorSidebarProps) => {
  // ... (existing state)
  const [certFile, setCertFile] = useState<File | null>(null);
  const [certPassword, setCertPassword] = useState("");
  const [certReason, setCertReason] = useState("");
  const [certLocation, setCertLocation] = useState("");
  const [certContact, setCertContact] = useState("");
  const [certCollapsed, setCertCollapsed] = useState(true);

  const {
    // ... (existing destructuring)
    onEditCertificate,
  } = data;

  const handleApplyCertificate = async () => {
    if (!certFile || !pdfDocument) return;
    
    // In a real scenario, we'd need the original File object. 
    // This is a simplified call for the prototype.
    // onEditCertificate({ ... });
  };

  return (
    <>
      <Stack style={{ height: "100%", display: "flex" }} gap={0}>
        <ScrollArea style={{ flex: 1 }} offsetScrollbars>
          <Stack gap="md">
            {/* ... (existing panels) */}

            <ToolStep
              title={t("pdfTextEditor.options.certificate.title", "Digital Certificate")}
              isCollapsed={certCollapsed}
              onCollapsedClick={() => setCertCollapsed(!certCollapsed)}
            >
              <Stack gap="sm">
                <Divider />
                <Text size="xs" c="dimmed">
                  {t("pdfTextEditor.options.certificate.description", "Optionally re-sign the document with a new certificate.")}
                </Text>
                
                <input 
                  type="file" 
                  accept=".p12,.pfx" 
                  onChange={(e) => setCertFile(e.target.files?.[0] || null)}
                  className="text-xs"
                />

                <Stack gap={4}>
                  <Text size="xs" fw={500}>{t("cert.password", "Password")}</Text>
                  <input 
                    type="password" 
                    value={certPassword} 
                    onChange={(e) => setCertPassword(e.target.value)}
                    className="bg-zinc-900 border border-zinc-800 p-2 rounded text-xs"
                  />
                </Stack>

                <Stack gap={4}>
                  <Text size="xs" fw={500}>{t("cert.reason", "Reason")}</Text>
                  <input 
                    type="text" 
                    value={certReason} 
                    onChange={(e) => setCertReason(e.target.value)}
                    className="bg-zinc-900 border border-zinc-800 p-2 rounded text-xs"
                  />
                </Stack>

                <Button 
                  size="xs" 
                  variant="light" 
                  color="blue"
                  disabled={!certFile}
                  onClick={handleApplyCertificate}
                >
                  {t("pdfTextEditor.actions.resign", "Re-sign with Certificate")}
                </Button>
              </Stack>
            </ToolStep>

            {/* ... (existing FontStatusPanel) */}
          </Stack>
        </ScrollArea>
        {/* ... (existing footer) */}
      </Stack>
    </>
  );
};

        <Group gap="xs" wrap="nowrap" p="md">
          <Button
            variant="filled"
            onClick={onSaveToWorkbench}
            loading={isSavingToWorkbench}
            disabled={!hasDocument || !hasChanges || isConverting}
            style={{ flex: 1 }}
          >
            {t("pdfTextEditor.actions.applyChanges", "Apply Changes")}
          </Button>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon
                variant="default"
                size="lg"
                disabled={!hasDocument || isConverting}
              >
                <MoreHorizIcon fontSize="small" />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<FileDownloadIcon fontSize="small" />}
                onClick={() => onGeneratePdf()}
                disabled={!hasChanges || isGeneratingPdf}
              >
                {t("pdfTextEditor.actions.downloadCopy", "Download Copy")}
              </Menu.Item>
              <Menu.Item
                leftSection={<AutorenewIcon fontSize="small" />}
                onClick={onReset}
                color="red"
              >
                {t("pdfTextEditor.actions.reset", "Reset Changes")}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Stack>

      {/* Mode Change Confirmation Modal */}
      <Modal
        opened={pendingModeChange !== null}
        onClose={handleCancelModeChange}
        title={t("pdfTextEditor.modeChange.title", "Confirm Mode Change")}
        centered
      >
        <Stack gap="md">
          <Text>
            {t(
              "pdfTextEditor.modeChange.warning",
              "Changing the text grouping mode will reset all unsaved changes. Are you sure you want to continue?",
            )}
          </Text>
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={handleCancelModeChange}>
              {t("pdfTextEditor.modeChange.cancel", "Cancel")}
            </Button>
            <Button color="red" onClick={handleConfirmModeChange}>
              {t("pdfTextEditor.modeChange.confirm", "Reset and Change Mode")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
};

export default PdfTextEditorSidebar;
