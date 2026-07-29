package stirling.software.SPDF.controller.api.security;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import stirling.software.SPDF.model.api.security.EditCertificateRequest;
import stirling.software.SPDF.util.WebResponseUtils;

@RestController
@RequestMapping("/api/v1/security")
@Slf4j
@RequiredArgsConstructor
@Tag(name = "Security", description = "Security APIs")
public class CertificateEditController {

    private final CertSignController certSignController;

    @PostMapping(value = "/edit-certificate", consumes = "multipart/form-data")
    @Operation(
            summary = "Edit PDF certificate info",
            description = "Re-signs a PDF with modified certificate information like reason, location, and contact info."
    )
    public ResponseEntity<byte[]> editCertificate(@ModelAttribute EditCertificateRequest request) throws Exception {
        // Reuse CertSignController's logic for consistency
        return certSignController.signPDFWithCert(
            request.getFileInput(),
            request.getCertFile(),
            request.getCertPassword(),
            request.getReason(),
            request.getLocation(),
            request.getContactInfo(),
            0, 0, 0, 1, // Default visual params (not used if hidden, but required by API)
            null, // No signature image
            null // No specific page
        );
    }
}
