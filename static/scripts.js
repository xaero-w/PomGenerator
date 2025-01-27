function savePomContent() {
    const generatedPom = document.getElementById("generated-pom").value;
    const fullPom = document.getElementById("full-pom");
    const hiddenFullPom = document.getElementById("hidden-full-pom");

    // Передаем отредактированные данные в поле "Full POM Template"
    fullPom.value = generatedPom;

    // Обновляем скрытое поле для формы отправки
    hiddenFullPom.value = generatedPom;

    // Показываем секцию "Full POM Template"
    const fullPomSection = document.getElementById("full-pom-section");
    fullPomSection.classList.remove("hidden");
    fullPomSection.classList.add("visible");
}
