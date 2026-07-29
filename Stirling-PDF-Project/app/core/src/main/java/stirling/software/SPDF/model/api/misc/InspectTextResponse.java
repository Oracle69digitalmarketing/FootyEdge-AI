package stirling.software.SPDF.model.api.misc;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import stirling.software.SPDF.model.json.PdfJsonTextElement;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InspectTextResponse {
    private List<PdfJsonTextElement> textRuns;
}
