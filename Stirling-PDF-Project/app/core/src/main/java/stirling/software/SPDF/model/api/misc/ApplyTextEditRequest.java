package stirling.software.SPDF.model.api.misc;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.web.multipart.MultipartFile;
import stirling.software.SPDF.model.json.PdfJsonTextElement;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ApplyTextEditRequest {
    @Schema(description = "The PDF file to edit")
    private MultipartFile fileInput;

    @Schema(description = "List of text runs to replace")
    private String editsJson;
}
