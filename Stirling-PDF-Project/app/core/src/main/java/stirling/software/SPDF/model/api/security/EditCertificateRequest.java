package stirling.software.SPDF.model.api.security;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.web.multipart.MultipartFile;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EditCertificateRequest {
    @Schema(description = "The PDF file to edit")
    private MultipartFile fileInput;

    @Schema(description = "New certificate password")
    private String certPassword;

    @Schema(description = "New reason for signing")
    private String reason;

    @Schema(description = "New location of signing")
    private String location;

    @Schema(description = "New contact info")
    private String contactInfo;
    
    @Schema(description = "The P12 certificate file")
    private MultipartFile certFile;
}
